from ten import (
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
)

import json
from typing import Generator, List
from http import HTTPStatus
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

        # workaround to speed up the embedding process,
        # should be replace by https://help.aliyun.com/zh/model-studio/developer-reference/text-embedding-batch-api?spm=a2c4g.11186623.0.0.24cb7453KSjdhC
        # once v3 models supported
        self.parallel = 10

    def on_start(self, ten: TenEnv) -> None:
        ten.log_info("on_start")
        self.api_key = self.get_property_string(ten, "api_key", self.api_key)
        self.model = self.get_property_string(ten, "model", self.api_key)

        # lazy import packages which requires long time to load
        global dashscope  # pylint: disable=global-statement
        import dashscope

        dashscope.api_key = self.api_key

        for i in range(self.parallel):
            thread = threading.Thread(target=self.async_handler, args=[i, ten])
            thread.start()
            self.threads.append(thread)

        ten.on_start_done()

    def async_handler(self, index: int, ten: TenEnv):
        ten.log_info(f"async_handler {index} statend")

        while not self.stop:
            cmd = self.queue.get()
            if cmd is None:
                break

            cmd_name = cmd.get_name()
            start_time = datetime.now()
            ten.log_info(f"async_handler {index} processing cmd {cmd_name}")

            if cmd_name == CMD_EMBED:
                cmd_result = self.call_with_str(cmd.get_property_string("input"), ten)
                ten.return_result(cmd_result, cmd)
            elif cmd_name == CMD_EMBED_BATCH:
                inputs_list = json.loads(cmd.get_property_to_json("inputs"))
                cmd_result = self.call_with_strs(inputs_list, ten)
                ten.return_result(cmd_result, cmd)
            else:
                ten.log_warn("unknown cmd {cmd_name}")

            ten.log_info(
                f"async_handler {index} finished processing cmd {cmd_name}, cost {int((datetime.now() - start_time).total_seconds() * 1000)}ms"
            )

        ten.log_info(f"async_handler {index} stopped")

    def call_with_str(self, message: str, ten: TenEnv) -> CmdResult:
        start_time = datetime.now()
        # pylint: disable=undefined-variable
        response = dashscope.TextEmbedding.call(model=self.model, input=message)
        ten.log_info(
            f"embedding call finished for input [{message}], status_code {response.status_code}, cost {int((datetime.now() - start_time).total_seconds() * 1000)}ms"
        )

        if response.status_code == HTTPStatus.OK:
            cmd_result = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_from_json(
                FIELD_KEY_EMBEDDING,
                json.dumps(response.output["embeddings"][0]["embedding"]),
            )
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

    def call_with_strs(self, messages: List[str], ten: TenEnv) -> CmdResult:
        start_time = datetime.now()
        result = None  # merge the results.
        batch_counter = 0
        for batch in self.batched(messages):
            # pylint: disable=undefined-variable
            response = dashscope.TextEmbedding.call(model=self.model, input=batch)
            # ten.log_info("%s Received %s", batch, response)
            if response.status_code == HTTPStatus.OK:
                if result is None:
                    result = response.output
                else:
                    for emb in response.output["embeddings"]:
                        emb["text_index"] += batch_counter
                        result["embeddings"].append(emb)
            else:
                ten.log_error("call %s failed, errmsg: %s", batch, response)
            batch_counter += len(batch)

        ten.log_info(
            f"embedding call finished for inputs len {len(messages)}, batch_counter {batch_counter}, results len {len(result['embeddings'])}, cost {int((datetime.now() - start_time).total_seconds() * 1000)}ms "
        )
        if result is not None:
            cmd_result = CmdResult.create(StatusCode.OK)

            # too slow `set_property_to_json`, so use `set_property_string` at the moment as workaround
            # will be replaced once `set_property_to_json` improved
            cmd_result.set_property_string(
                FIELD_KEY_EMBEDDINGS, json.dumps(result["embeddings"])
            )
            return cmd_result
        else:
            cmd_result = CmdResult.create(StatusCode.ERROR)
            cmd_result.set_property_string(FIELD_KEY_MESSAGE, "All batch failed")
            ten.log_error("All batch failed")
            return cmd_result

    def on_stop(self, ten: TenEnv) -> None:
        ten.log_info("on_stop")
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

        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()

        if cmd_name in [CMD_EMBED, CMD_EMBED_BATCH]:
            # // embed
            # {
            #     "name": "embed",
            #     "input": "hello"
            # }

            # // embed_batch
            # {
            #     "name": "embed_batch",
            #     "inputs": ["hello", ...]
            # }

            self.queue.put(cmd)
        else:
            ten.log_warn(f"unknown cmd {cmd_name}")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            ten.return_result(cmd_result, cmd)

    def get_property_string(self, ten: TenEnv, key, default):
        try:
            return ten.get_property_string(key)
        except Exception as e:
            ten.log_warn(f"err: {e}")
            return default
