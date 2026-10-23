#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from moss import MossClient, QueryOptions
from pydantic import BaseModel
from ten_ai_base.llm_tool import AsyncLLMToolBaseExtension
from ten_ai_base.types import (
    LLMToolMetadata,
    LLMToolMetadataParameter,
    LLMToolResult,
)
from ten_runtime import AsyncTenEnv

TOOL_NAME = "search_knowledge_base"


class MossToolConfig(BaseModel):
    project_id: str = ""
    project_key: str = ""
    index_name: str = ""
    top_k: int = 3


class MossToolExtension(AsyncLLMToolBaseExtension):
    """Searches a Moss index held in memory, so a query makes no network call."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.config = MossToolConfig()
        self.client: MossClient | None = None

    async def on_start(self, ten_env: AsyncTenEnv) -> None:
        config_json, _ = await ten_env.get_property_to_json(None)
        self.config = MossToolConfig.model_validate_json(config_json)
        try:
            self.client = MossClient(
                self.config.project_id, self.config.project_key
            )
            await self.client.load_index(
                self.config.index_name, auto_refresh=True
            )
        except Exception as e:
            ten_env.log_error(f"Moss index not loaded, tool disabled: {e}")
            return
        await super().on_start(ten_env)

    async def on_stop(self, ten_env: AsyncTenEnv) -> None:
        if self.client:
            await self.client.close()
        await super().on_stop(ten_env)

    def get_tool_metadata(self, ten_env: AsyncTenEnv) -> list[LLMToolMetadata]:
        return [
            LLMToolMetadata(
                name=TOOL_NAME,
                description="Search the knowledge base for facts that answer the user's question.",
                parameters=[
                    LLMToolMetadataParameter(
                        name="query",
                        type="string",
                        description="The user's question or a focused search query.",
                        required=True,
                    )
                ],
            )
        ]

    async def run_tool(
        self, ten_env: AsyncTenEnv, name: str, args: dict
    ) -> LLMToolResult | None:
        result = await self.client.query(
            self.config.index_name,
            args.get("query", ""),
            QueryOptions(top_k=self.config.top_k),
        )
        ten_env.log_info(
            f"Moss: {len(result.docs)} results in {result.time_taken_ms} ms"
        )
        return {
            "type": "llmresult",
            "content": "\n\n".join(doc.text for doc in result.docs),
        }
