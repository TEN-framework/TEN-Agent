from typing import Any, List
import threading
from llama_index.core.embeddings import BaseEmbedding
from .log import logger
import json
from rte import (
    Cmd,
    CmdResult,
)

EMBED_CMD = "embed"


def embed_from_resp(cmd_result: CmdResult) -> List[float]:
    embedding_output_json = cmd_result.get_property_to_json("embedding")
    return json.loads(embedding_output_json)


class ASTRAEmbedding(BaseEmbedding):
    rte: Any

    def __init__(self, rte):
        """Creates a new ASTRA embedding interface."""
        super().__init__()
        self.rte = rte

    @classmethod
    def class_name(cls) -> str:
        return "astra_embedding"

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _get_query_embedding(self, query: str) -> List[float]:
        logger.info(
            "ASTRAEmbedding generate embeddings for the query: {}".format(query)
        )
        wait_event = threading.Event()
        resp: List[float]

        def callback(_, result):
            nonlocal resp
            nonlocal wait_event

            logger.debug("ASTRAEmbedding embedding received")
            resp = embed_from_resp(result)
            wait_event.set()

        cmd_out = Cmd.create(EMBED_CMD)
        cmd_out.set_property_string("input", query)

        self.rte.send_cmd(cmd_out, callback)
        wait_event.wait()
        return resp

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_query_embedding(text)

    # for texts embedding, will not be called in this module
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        logger.warning("not implemented")
        return []
