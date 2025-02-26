from typing import Any, List
import threading
from llama_index.core.embeddings import BaseEmbedding
import json
from ten import (
    Cmd,
    CmdResult,
    TenEnv,
)

EMBED_CMD = "embed"


def embed_from_resp(cmd_result: CmdResult) -> List[float]:
    embedding_output_json = cmd_result.get_property_to_json("embedding")
    return json.loads(embedding_output_json)


class LlamaEmbedding(BaseEmbedding):
    ten: Any

    def __init__(self, ten: TenEnv):
        """Creates a new Llama embedding interface."""
        super().__init__()
        self.ten = ten

    @classmethod
    def class_name(cls) -> str:
        return "llama_embedding"

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> List[float]:
        self.ten.log_info(f"LlamaEmbedding generate embeddings for the query: {query}")
        wait_event = threading.Event()
        resp: List[float]

        def callback(_, result, __):
            nonlocal resp
            nonlocal wait_event

            self.ten.log_debug("LlamaEmbedding embedding received")
            resp = embed_from_resp(result)
            wait_event.set()

        cmd_out = Cmd.create(EMBED_CMD)
        cmd_out.set_property_string("input", query)

        self.ten.send_cmd(cmd_out, callback)
        wait_event.wait()
        return resp

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_query_embedding(text)

    # for texts embedding, will not be called in this module
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        self.ten.log_warn("not implemented")
        return []
