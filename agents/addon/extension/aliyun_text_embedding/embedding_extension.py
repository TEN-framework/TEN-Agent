from rte import (
    Extension,
    RteEnv,
    Cmd,
    StatusCode,
    CmdResult,
)

import dashscope
import json
from typing import Generator, List
from http import HTTPStatus
from .log import logger
import threading, queue
from datetime import datetime

CMD_EMBED = "embed"
CMD_EMBED_BATCH = "embed_batch"

FIELD_KEY_EMBEDDING = "embedding"
FIELD_KEY_EMBEDDINGS = "embeddings"
FIELD_KEY_MESSAGE = "message"
FIELD_KEY_CODE = "code"

DASHSCOPE_MAX_BATCH_SIZE = 6


class EmbeddingExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.api_key = ""
        self.model = ""

        self.stop = False
        self.queue = queue.Queue()
        self.threads = []

        # TODO: workaround to speed up the embedding process,
        # should be replace by https://help.aliyun.com/zh/model-studio/developer-reference/text-embedding-batch-api?spm=a2c4g.11186623.0.0.24cb7453KSjdhC
        # once v3 models supported
        self.parallel = 10

    def on_start(self, rte: RteEnv) -> None:
        logger.info("on_start")
        self.api_key = self.get_property_string(rte, "api_key", self.api_key)
        self.model = self.get_property_string(rte, "model", self.api_key)

        dashscope.api_key = self.api_key

        for i in range(self.parallel):
            thread = threading.Thread(target=self.async_handler, args=[i, rte])
            thread.start()
            self.threads.append(thread)

        rte.on_start_done()

    def async_handler(self, index: int, rte: RteEnv):
        logger.info("async_handler {} started".format(index))

        while not self.stop:
            cmd = self.queue.get()
            if cmd is None:
                break

            cmd_name = cmd.get_name()
            start_time = datetime.now()
            logger.info(
                    "async_handler {} processing cmd {}".format(index, cmd_name))
            
            if cmd_name == CMD_EMBED:
                cmd_result = self.call_with_str(cmd.get_property_string("input"))
                rte.return_result(cmd_result, cmd)
            elif cmd_name == CMD_EMBED_BATCH:
                list = json.loads(cmd.get_property_to_json("inputs"))
                cmd_result = self.call_with_strs(list)
                rte.return_result(cmd_result, cmd)
            else:
                logger.warning("unknown cmd {}".format(cmd_name))
            
            logger.info(
                    "async_handler {} finished processing cmd {}, cost {}ms".format(index, cmd_name, int((datetime.now() - start_time).total_seconds() * 1000)))

        logger.info("async_handler {} stopped".format(index))

    def call_with_str(self, message: str) -> CmdResult:
        start_time = datetime.now()
        response = dashscope.TextEmbedding.call(model=self.model, input=message)
        logger.info("embedding call finished for input [{}], status_code {}, cost {}ms".format(message, response.status_code, int((datetime.now() - start_time).total_seconds() * 1000)))

        if response.status_code == HTTPStatus.OK:
            cmd_result = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_from_json(FIELD_KEY_EMBEDDING, response.output["embeddings"][0]["embedding"])
            return cmd_result
        else:
            cmd_result = CmdResult.create(StatusCode.ERROR)
            cmd_result.set_property_string(FIELD_KEY_CODE, response.status_code)
            cmd_result.set_property_string(FIELD_KEY_MESSAGE, response.message)
            return cmd_result

    def batched(
        self, inputs: List, batch_size: int = DASHSCOPE_MAX_BATCH_SIZE
    ) -> Generator[List, None, None]:
        for i in range(0, len(inputs), batch_size):
            yield inputs[i : i + batch_size]

    def call_with_strs(self, messages: List[str]) -> CmdResult:
        start_time = datetime.now()
        result = None  # merge the results.
        batch_counter = 0
        for batch in self.batched(messages):
            response = dashscope.TextEmbedding.call(model=self.model, input=batch)
            # logger.info("%s Received %s", batch, response)
            if response.status_code == HTTPStatus.OK:
                if result is None:
                    result = response.output
                else:
                    for emb in response.output["embeddings"]:
                        emb["text_index"] += batch_counter
                        result["embeddings"].append(emb)
            else:
                logger.error("call %s failed, errmsg: %s", batch, response)
            batch_counter += len(batch)

        logger.info("embedding call finished for inputs len {}, batch_counter {}, results len {}, cost {}ms ".format(len(messages), batch_counter, len(result["embeddings"]), int((datetime.now() - start_time).total_seconds() * 1000)))
        if result is not None:
            cmd_result = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_string(FIELD_KEY_EMBEDDINGS, json.dumps(result["embeddings"]))
            return cmd_result
        else:
            cmd_result = CmdResult.create(StatusCode.ERROR)
            cmd_result.set_property_string(FIELD_KEY_MESSAGE, "All batch failed")
            logger.error("All batch failed")
            return cmd_result

    def on_stop(self, rte: RteEnv) -> None:
        logger.info("on_stop")
        self.stop = True
        # clear queue
        while not self.queue.empty():
            self.queue.get()
        # put enough None to stop all threads
        for thread in self.threads:
            self.queue.put(None)
        for thread in self.threads:
            thread.join()
        self.threads = []

        rte.on_stop_done()

    def on_cmd(self, rte: RteEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()

        if cmd_name in [CMD_EMBED, CMD_EMBED_BATCH]:
            """
            // embed
            {
                "name": "embed",
                "input": "hello"
            }

            // embed_batch
            {
                "name": "embed_batch",
                "inputs": ["hello", ...]  
            }
            """

            self.queue.put(cmd)
        else:
            logger.warning("unknown cmd {}".format(cmd_name))
            cmd_result = CmdResult.create(StatusCode.ERROR)
            rte.return_result(cmd_result, cmd)

    def get_property_string(self, rte: RteEnv, key, default):
        try:
            return rte.get_property_string(key)
        except Exception as e:
            logger.warning(f"err: {e}")
            return default
