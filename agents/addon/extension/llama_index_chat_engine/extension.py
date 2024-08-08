#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from rte import (
    Extension,
    RteEnv,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
)
from .log import logger
from .astra_llm import ASTRALLM
from .astra_retriever import ASTRARetriever
import queue, threading
from datetime import datetime
from llama_index.core.chat_engine import SimpleChatEngine, ContextChatEngine
from llama_index.core.storage.chat_store import SimpleChatStore
from llama_index.core.memory import ChatMemoryBuffer

PROPERTY_CHAT_MEMORY_TOKEN_LIMIT = "chat_memory_token_limit"
PROPERTY_GREETING = "greeting"


class LlamaIndexExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.queue = queue.Queue()
        self.thread = None
        self.stop = False

        self.collection_name = ""
        self.outdate_ts = datetime.now()
        self.chat_memory_token_limit = 3000
        self.chat_memory = None

    def _send_text_data(self, rte: RteEnv, text: str, end_of_segment: bool):
        try:
            output_data = Data.create("text_data")
            output_data.set_property_string("text", text)
            output_data.set_property_bool("end_of_segment", end_of_segment)
            rte.send_data(output_data)
            logger.info("text [{}] end_of_segment {} sent".format(text, end_of_segment))
        except Exception as err:
            logger.info(
                "text [{}] end_of_segment {} send failed, err {}".format(
                    text, end_of_segment, err
                )
            )

    def on_start(self, rte: RteEnv) -> None:
        logger.info("on_start")

        greeting = None
        try:
            greeting = rte.get_property_string(PROPERTY_GREETING)
        except Exception as err:
            logger.warning(f"get {PROPERTY_GREETING} property failed, err: {err}")

        try:
            self.chat_memory_token_limit = rte.get_property_int(
                PROPERTY_CHAT_MEMORY_TOKEN_LIMIT
            )
        except Exception as err:
            logger.warning(
                f"get {PROPERTY_CHAT_MEMORY_TOKEN_LIMIT} property failed, err: {err}"
            )

        self.thread = threading.Thread(target=self.async_handle, args=[rte])
        self.thread.start()

        # enable chat memory
        self.chat_memory = ChatMemoryBuffer.from_defaults(
            token_limit=self.chat_memory_token_limit,
            chat_store=SimpleChatStore(),
        )

        # Send greeting if available
        if greeting is not None:
            self._send_text_data(rte, greeting, True)

        rte.on_start_done()

    def on_stop(self, rte: RteEnv) -> None:
        logger.info("on_stop")

        self.stop = True
        self.flush()
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        self.chat_memory = None

        rte.on_stop_done()

    def on_cmd(self, rte: RteEnv, cmd: Cmd) -> None:

        cmd_name = cmd.get_name()
        logger.info("on_cmd {}".format(cmd_name))
        if cmd_name == "file_chunked":
            coll = cmd.get_property_string("collection_name")
            self.collection_name = coll

            file_chunked_text = "Your document has been processed. Please wait a moment while we process your document for you. "
            self._send_text_data(rte, file_chunked_text, True)
        elif cmd_name == "file_downloaded":
            file_downloaded_text = "Your document has been received. Please wait a moment while we process it for you.  "
            self._send_text_data(rte, file_downloaded_text, True)
        elif cmd_name == "flush":
            self.flush()
            rte.send_cmd(Cmd.create("flush"), None)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "ok")
        rte.return_result(cmd_result, cmd)

    def on_data(self, rte: RteEnv, data: Data) -> None:
        is_final = data.get_property_bool("is_final")
        if not is_final:
            logger.info("on_data ignore non final")
            return

        inputText = data.get_property_string("text")
        if len(inputText) == 0:
            logger.info("on_data ignore empty text")
            return

        ts = datetime.now()

        logger.info("on_data text [%s], ts [%s]", inputText, ts)
        self.queue.put((inputText, ts))

    def async_handle(self, rte: RteEnv):
        logger.info("async_handle started")
        while not self.stop:
            try:
                value = self.queue.get()
                if value is None:
                    break
                input_text, ts = value
                if ts < self.outdate_ts:
                    logger.info(
                        "text [%s] ts [%s] dropped due to outdated", input_text, ts
                    )
                    continue
                logger.info("process input text [%s] ts [%s]", input_text, ts)

                # prepare chat engine
                chat_engine = None
                if len(self.collection_name) > 0:
                    chat_engine = ContextChatEngine.from_defaults(
                        llm=ASTRALLM(rte=rte),
                        retriever=ASTRARetriever(rte=rte, coll=self.collection_name),
                        memory=self.chat_memory,
                        system_prompt=(
                            "You are an expert Q&A system that is trusted around the world.\n"
                            "Always answer the query using the provided context information, "
                            "and not prior knowledge.\n"
                            "Some rules to follow:\n"
                            "1. Never directly reference the given context in your answer.\n"
                            "2. Avoid statements like 'Based on the context, ...' or "
                            "'The context information ...' or anything along "
                            "those lines."
                        ),
                    )
                else:
                    chat_engine = SimpleChatEngine.from_defaults(
                        llm=ASTRALLM(rte=rte),
                        system_prompt="You are an expert Q&A system that is trusted around the world.\n",
                        memory=self.chat_memory,
                    )

                resp = chat_engine.stream_chat(input_text)
                for cur_token in resp.response_gen:
                    if self.stop:
                        break
                    if ts < self.outdate_ts:
                        logger.info(
                            "stream_chat coming responses dropped due to outdated for input text [%s] ts [%s] ",
                            input_text,
                            ts,
                        )
                        break
                    text = str(cur_token)

                    # send out
                    self._send_text_data(rte, text, False)

                # send out end_of_segment
                self._send_text_data(rte, "", True)
            except Exception as e:
                logger.exception(e)
        logger.info("async_handle stoped")

    def flush(self):
        self.outdate_ts = datetime.now()
        while not self.queue.empty():
            self.queue.get()
