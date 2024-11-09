import time, json, threading
from typing import Any, List
from llama_index.core.schema import QueryBundle, TextNode
from llama_index.core.schema import NodeWithScore
from llama_index.core.retrievers import BaseRetriever

from .log import logger
from .llama_embedding import LlamaEmbedding
from ten import (
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
)


def format_node_result(cmd_result: CmdResult) -> List[NodeWithScore]:
    logger.info("LlamaRetriever retrieve response {}".format(cmd_result.to_json()))
    status = cmd_result.get_status_code()
    try:
        contents_json = cmd_result.get_property_to_json("response")
    except Exception as e:
        logger.warning(f"Failed to get response from cmd_result: {e}")
        return [
            NodeWithScore(
                node=TextNode(),
                score=0.0,
            )
        ]
    contents = json.loads(contents_json)
    if status != StatusCode.OK or len(contents) == 0:
        return [
            NodeWithScore(
                node=TextNode(),
                score=0.0,
            )
        ]

    nodes = []
    for result in contents:
        text_node = TextNode(
            text=result["content"],
        )
        nodes.append(NodeWithScore(node=text_node, score=result["score"]))
    return nodes


class LlamaRetriever(BaseRetriever):
    ten: Any
    embed_model: LlamaEmbedding

    def __init__(self, ten: TenEnv, coll: str):
        super().__init__()
        try:
            self.ten = ten
            self.embed_model = LlamaEmbedding(ten=ten)
            self.collection_name = coll
        except Exception as e:
            logger.error(f"Failed to initialize LlamaRetriever: {e}")

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        logger.info("LlamaRetriever retrieve: {}".format(query_bundle.to_json))

        wait_event = threading.Event()
        resp: List[NodeWithScore] = []

        def cmd_callback(_, result):
            nonlocal resp
            nonlocal wait_event
            resp = format_node_result(result)
            wait_event.set()
            logger.debug("LlamaRetriever callback done")

        embedding = self.embed_model.get_query_embedding(query=query_bundle.query_str)

        query_cmd = Cmd.create("query_vector")
        query_cmd.set_property_string("collection_name", self.collection_name)
        query_cmd.set_property_int("top_k", 3)  # TODO: configable
        query_cmd.set_property_from_json("embedding", json.dumps(embedding))
        logger.info(
            "LlamaRetriever send_cmd, collection_name: {}, embedding len: {}".format(
                self.collection_name, len(embedding)
            )
        )
        self.ten.send_cmd(query_cmd, cmd_callback)

        wait_event.wait()
        return resp
