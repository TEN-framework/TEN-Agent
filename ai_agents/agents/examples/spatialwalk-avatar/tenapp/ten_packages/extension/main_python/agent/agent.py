import asyncio
import json
from typing import Awaitable, Callable, Optional
from .llm_exec import LLMExec
from ten_runtime import AsyncTenEnv, Cmd, CmdResult, Data, StatusCode
from ten_ai_base.const import CMD_PROPERTY_RESULT
from ten_ai_base.types import LLMToolMetadata, LLMToolResult
from .events import *


class Agent:
    def __init__(self, ten_env: AsyncTenEnv):
        self.ten_env: AsyncTenEnv = ten_env
        self.stopped = False

        # Callback registry
        self._callbacks: dict[
            AgentEvent, list[Callable[[AgentEvent], Awaitable]]
        ] = {}

        # Queues for ordered processing
        self._asr_queue: asyncio.Queue[ASRResultEvent] = asyncio.Queue()
        self._llm_queue: asyncio.Queue[LLMResponseEvent] = asyncio.Queue()

        # Current consumer tasks
        self._asr_consumer: Optional[asyncio.Task] = None
        self._llm_consumer: Optional[asyncio.Task] = None
        self._llm_active_task: Optional[asyncio.Task] = (
            None  # currently running handler
        )
        self._local_tool_handlers: dict[
            str, Callable[[dict], Awaitable[LLMToolResult | None]]
        ] = {}

        self.llm_exec = LLMExec(ten_env)
        self.llm_exec.on_response = (
            self._on_llm_response
        )  # callback handled internally
        self.llm_exec.on_reasoning_response = (
            self._on_llm_reasoning_response
        )  # callback handled internally

        # Start consumers
        self._asr_consumer = asyncio.create_task(self._consume_asr())
        self._llm_consumer = asyncio.create_task(self._consume_llm())

    # === Register handlers ===
    def on(
        self,
        event_type: AgentEvent,
        handler: Callable[[AgentEvent], Awaitable] = None,
    ):
        """
        Register a callback for a given event type.

        Can be used in two ways:
        1) agent.on(EventType, handler)
        2) @agent.on(EventType)
           async def handler(event: EventType): ...
        """

        def decorator(func: Callable[[AgentEvent], Awaitable]):
            self._callbacks.setdefault(event_type, []).append(func)
            return func

        if handler is None:
            return decorator
        else:
            return decorator(handler)

    async def _dispatch(self, event: AgentEvent):
        """Dispatch event to registered handlers sequentially."""
        for etype, handlers in self._callbacks.items():
            if isinstance(event, etype):
                for h in handlers:
                    try:
                        await h(event)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        self.ten_env.log_error(
                            f"Handler error for {etype}: {e}"
                        )

    # === Consumers ===
    async def _consume_asr(self):
        while not self.stopped:
            event = await self._asr_queue.get()
            await self._dispatch(event)

    async def _consume_llm(self):
        while not self.stopped:
            event = await self._llm_queue.get()
            # Run handler as a task so we can cancel mid-flight
            self._llm_active_task = asyncio.create_task(self._dispatch(event))
            try:
                await self._llm_active_task
            except asyncio.CancelledError:
                self.ten_env.log_info("[Agent] Active LLM task cancelled")
            finally:
                self._llm_active_task = None

    # === Emit events ===
    async def _emit_asr(self, event: ASRResultEvent):
        await self._asr_queue.put(event)

    async def _emit_llm(self, event: LLMResponseEvent):
        await self._llm_queue.put(event)

    async def _emit_direct(self, event: AgentEvent):
        await self._dispatch(event)

    # === Incoming from runtime ===
    async def on_cmd(self, cmd: Cmd):
        try:
            name = cmd.get_name()
            if name == "on_user_joined":
                await self._emit_direct(UserJoinedEvent())
            elif name == "on_user_left":
                await self._emit_direct(UserLeftEvent())
            elif name == "tool_register":
                tool_json, err = cmd.get_property_to_json("tool")
                if err:
                    raise RuntimeError(f"Invalid tool metadata: {err}")
                tool = LLMToolMetadata.model_validate_json(tool_json)
                await self._emit_direct(
                    ToolRegisterEvent(
                        tool=tool, source=cmd.get_source().extension_name
                    )
                )
            elif name == "tool_call":
                tool_name, err = cmd.get_property_string("name")
                if err:
                    raise RuntimeError(f"Invalid tool_call name: {err}")
                args_json, err = cmd.get_property_to_json("arguments")
                if err:
                    raise RuntimeError(
                        f"Invalid tool_call arguments for {tool_name}: {err}"
                    )
                args = json.loads(args_json) if args_json else {}
                handler = self._local_tool_handlers.get(tool_name)
                if not handler:
                    raise RuntimeError(
                        f"Unhandled local tool_call: {tool_name}"
                    )
                result = await handler(args)
                cmd_result = CmdResult.create(StatusCode.OK, cmd)
                if result is not None:
                    cmd_result.set_property_from_json(
                        CMD_PROPERTY_RESULT, json.dumps(result)
                    )
                await self.ten_env.return_result(cmd_result)
                return
            else:
                self.ten_env.log_warn(f"Unhandled cmd: {name}")

            await self.ten_env.return_result(
                CmdResult.create(StatusCode.OK, cmd)
            )
        except Exception as e:
            self.ten_env.log_error(f"on_cmd error: {e}")
            await self.ten_env.return_result(
                CmdResult.create(StatusCode.ERROR, cmd)
            )

    async def on_data(self, data: Data):
        try:
            if data.get_name() == "asr_result":
                asr_json, _ = data.get_property_to_json(None)
                asr = json.loads(asr_json)
                await self._emit_asr(
                    ASRResultEvent(
                        text=asr.get("text", ""),
                        final=asr.get("final", False),
                        metadata=asr.get("metadata", {}),
                    )
                )
            else:
                self.ten_env.log_warn(f"Unhandled data: {data.get_name()}")
        except Exception as e:
            self.ten_env.log_error(f"on_data error: {e}")

    async def _on_llm_response(
        self, ten_env: AsyncTenEnv, delta: str, text: str, is_final: bool
    ):
        await self._emit_llm(
            LLMResponseEvent(delta=delta, text=text, is_final=is_final)
        )

    async def _on_llm_reasoning_response(
        self, ten_env: AsyncTenEnv, delta: str, text: str, is_final: bool
    ):
        """
        Internal callback for streaming LLM output, wrapped as an AgentEvent.
        """
        await self._emit_llm(
            LLMResponseEvent(
                delta=delta, text=text, is_final=is_final, type="reasoning"
            )
        )

    # === LLM control ===
    async def register_llm_tool(self, tool: LLMToolMetadata, source: str):
        """
        Register tools with the LLM.
        This method sends a command to register the provided tools.
        """
        await self.llm_exec.register_tool(tool, source)

    async def register_local_tool(
        self,
        tool: LLMToolMetadata,
        source: str,
        handler: Callable[[dict], Awaitable[LLMToolResult | None]],
    ):
        self._local_tool_handlers[tool.name] = handler
        await self.register_llm_tool(tool, source)

    async def queue_llm_input(self, text: str):
        """
        Queue a new message to the LLM context.
        This method sends the text input to the LLM for processing.
        """
        await self.llm_exec.queue_input(text)

    async def flush_llm(self):
        """
        Flush the LLM input queue.
        This will ensure that all queued inputs are processed.
        """
        await self.llm_exec.flush()

        # Clear queue
        while not self._llm_queue.empty():
            try:
                self._llm_queue.get_nowait()
                self._llm_queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Cancel active LLM task
        if self._llm_active_task and not self._llm_active_task.done():
            self._llm_active_task.cancel()
            try:
                await self._llm_active_task
            except asyncio.CancelledError:
                pass
            self._llm_active_task = None

    async def stop(self):
        """
        Stop the agent processing.
        This will stop the event queue and any ongoing tasks.
        """
        self.stopped = True
        await self.llm_exec.stop()
        await self.flush_llm()
        if self._asr_consumer:
            self._asr_consumer.cancel()
        if self._llm_consumer:
            self._llm_consumer.cancel()
