#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten_runtime import AsyncTenEnv, Cmd
from ten_ai_base.config import BaseConfig
from ten_ai_base.types import (
    LLMToolMetadata,
    LLMToolMetadataParameter,
    LLMToolResult,
    LLMToolResultLLMResult,
)
from ten_ai_base.llm_tool import AsyncLLMToolBaseExtension
from dataclasses import dataclass
import shlex

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

CMD_TOOL_REGISTER = "tool_register"
CMD_TOOL_CALL = "tool_call"
CMD_PROPERTY_NAME = "name"
CMD_PROPERTY_ARGS = "args"

TOOL_REGISTER_PROPERTY_NAME = "name"
TOOL_REGISTER_PROPERTY_DESCRIPTON = "description"
TOOL_REGISTER_PROPERTY_PARAMETERS = "parameters"
TOOL_CALLBACK = "callback"


@dataclass
class MCPClientConfig(BaseConfig):
    # SSE endpoint of a remote MCP server.
    url: str = ""

    # Command line of a local MCP server to launch and talk to over stdio,
    # e.g. "npx -y @modelcontextprotocol/server-filesystem /data".
    # Takes precedence over `url` when both are set.
    command: str = ""


class MCPClientExtension(AsyncLLMToolBaseExtension):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.ten_env = None
        self.config: MCPClientConfig = None
        self.session: ClientSession = None
        self.available_tools: list[LLMToolMetadata] = []

        self._streams_context = None
        self._session_context = None

    async def on_init(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_init")

    def _create_transport(self, ten_env: AsyncTenEnv):
        """Create the MCP transport selected by the configuration.

        `command` launches a local server and talks to it over stdio,
        `url` connects to a remote server over SSE. Returns None when
        neither is configured.
        """
        if self.config.command:
            argv = shlex.split(self.config.command)
            if not argv:
                ten_env.log_error(
                    "`command` is set but contains no executable"
                )
                return None

            ten_env.log_info(f"Starting MCP server over stdio: {argv}")
            return stdio_client(
                StdioServerParameters(command=argv[0], args=argv[1:])
            )

        if self.config.url:
            ten_env.log_info(
                f"Connecting to MCP server over SSE: {self.config.url}"
            )
            return sse_client(url=self.config.url)

        ten_env.log_error(
            "No MCP server configured. Set `command` for a local server "
            "over stdio, or `url` for a remote one over SSE."
        )
        return None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_start")

        self.config = await MCPClientConfig.create_async(ten_env=ten_env)
        ten_env.log_info(f"config: {self.config}")

        transport = self._create_transport(ten_env)
        if transport is not None:
            self._streams_context = transport
            # pylint: disable=no-member
            streams = await self._streams_context.__aenter__()
            # pylint: enable=no-member

            self._session_context = ClientSession(*streams)
            self.session: ClientSession = (
                await self._session_context.__aenter__()
            )

            # Initialize
            await self.session.initialize()

            response = await self.session.list_tools()

            ten_env.log_info(f"Connected to server with tools: {response}")
            # Convert JSON Schema parameters to LLMToolMetadataParameter format
            for tool in response.tools:
                parameters = []
                if "properties" in tool.inputSchema:
                    for param_name, param_schema in tool.inputSchema[
                        "properties"
                    ].items():
                        required = param_name in tool.inputSchema.get(
                            "required", []
                        )
                        param_type = param_schema.get("type", "string")
                        param_items = param_schema.get(
                            "items", {"type": "string"}
                        )
                        description = param_schema.get("title", param_name)

                        param = LLMToolMetadataParameter(
                            name=param_name,
                            type=param_type,
                            description=description,
                            required=required,
                        )

                        if param_type == "array":
                            param.items = param_items

                        parameters.append(param)

                self.available_tools.append(
                    LLMToolMetadata(
                        name=tool.name,
                        description=tool.description or "",
                        parameters=parameters,
                    )
                )
            await super().on_start(ten_env)

        self.ten_env = ten_env

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_stop")

        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            # pylint: disable=no-member
            await self._streams_context.__aexit__(None, None, None)
            # pylint: enable=no-member

    async def on_deinit(self, ten_env: AsyncTenEnv) -> None:
        ten_env.log_debug("on_deinit")

    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return self.available_tools

    async def on_cmd(self, ten_env: AsyncTenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        await super().on_cmd(ten_env, cmd)

    async def run_tool(
        self, ten_env: AsyncTenEnv, name: str, args: dict
    ) -> LLMToolResult | None:
        ten_env.log_info(f"run_tool name: {name}, args: {args}")

        result = await self.session.call_tool(name, args)

        ten_env.log_info(f"result: {result}")

        return LLMToolResultLLMResult(
            type="llmresult",
            content=result.model_dump_json(),
        )
