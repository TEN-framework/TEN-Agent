from typing import Any, Sequence
import json, queue
import threading

from llama_index.core.base.llms.types import (
    LLMMetadata,
    MessageRole,
    ChatMessage,
    ChatResponse,
    CompletionResponse,
    ChatResponseGen,
    CompletionResponseGen,
)

from llama_index.core.llms.callbacks import llm_chat_callback, llm_completion_callback

from llama_index.core.llms.custom import CustomLLM
from .log import logger
from ten import Cmd, StatusCode, CmdResult


def chat_from_llama_response(cmd_result: CmdResult) -> ChatResponse:
    status = cmd_result.get_status_code()
    if status != StatusCode.OK:
        return None
    text_data = cmd_result.get_property_string("text")
    return ChatResponse(message=ChatMessage(content=text_data))


def _messages_str_from_chat_messages(messages: Sequence[ChatMessage]) -> str:
    messages_list = []
    for message in messages:
        messages_list.append(
            {"role": message.role, "content": "{}".format(message.content)}
        )
    return json.dumps(messages_list, ensure_ascii=False)


class LlamaLLM(CustomLLM):
    ten: Any

    def __init__(self, ten):
        """Creates a new Llama model interface."""
        super().__init__()
        self.ten = ten

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            # TODO: fix metadata
            context_window=1024,
            num_output=512,
            model_name="llama_llm",
            is_chat_model=True,
        )

    @llm_chat_callback()
    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        logger.debug("LlamaLLM chat start")

        resp: ChatResponse
        wait_event = threading.Event()

        def callback(_, result):
            logger.debug("LlamaLLM chat callback done")
            nonlocal resp
            nonlocal wait_event
            resp = chat_from_llama_response(result)
            wait_event.set()

        messages_str = _messages_str_from_chat_messages(messages)

        cmd = Cmd.create("call_chat")
        cmd.set_property_string("messages", messages_str)
        cmd.set_property_bool("stream", False)
        logger.info(
            "LlamaLLM chat send_cmd {}, messages {}".format(
                cmd.get_name(), messages_str
            )
        )

        self.ten.send_cmd(cmd, callback)
        wait_event.wait()
        return resp

    @llm_completion_callback()
    def complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        logger.warning("LlamaLLM complete hasn't been implemented yet")

    @llm_chat_callback()
    def stream_chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponseGen:
        logger.debug("LlamaLLM stream_chat start")

        cur_tokens = ""
        resp_queue = queue.Queue()

        def gen() -> ChatResponseGen:
            while True:
                delta_text = resp_queue.get()
                if delta_text is None:
                    break

                yield ChatResponse(
                    message=ChatMessage(content=delta_text, role=MessageRole.ASSISTANT),
                    delta=delta_text,
                )

        def callback(_, result):
            nonlocal cur_tokens
            nonlocal resp_queue

            status = result.get_status_code()
            if status != StatusCode.OK:
                logger.warn("LlamaLLM stream_chat callback status {}".format(status))
                resp_queue.put(None)
                return

            cur_tokens = result.get_property_string("text")
            logger.debug("LlamaLLM stream_chat callback text [{}]".format(cur_tokens))
            resp_queue.put(cur_tokens)
            if result.get_is_final():
                resp_queue.put(None)

        messages_str = _messages_str_from_chat_messages(messages)

        cmd = Cmd.create("call_chat")
        cmd.set_property_string("messages", messages_str)
        cmd.set_property_bool("stream", True)
        logger.info(
            "LlamaLLM stream_chat send_cmd {}, messages {}".format(
                cmd.get_name(), messages_str
            )
        )
        self.ten.send_cmd(cmd, callback)
        return gen()

    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        logger.warning("LlamaLLM stream_complete hasn't been implemented yet")

    @classmethod
    def class_name(cls) -> str:
        return "llama_llm"
