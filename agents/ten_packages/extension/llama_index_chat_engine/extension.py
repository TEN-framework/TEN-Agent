#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from ten import (
    Extension,
    TenEnv,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
)
from .log import logger
import queue, threading
from datetime import datetime

PROPERTY_CHAT_MEMORY_TOKEN_LIMIT = "chat_memory_token_limit"
PROPERTY_GREETING = "greeting"

TASK_TYPE_CHAT_REQUEST = "chat_request"
TASK_TYPE_GREETING = "greeting"


class LlamaIndexExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.queue = queue.Queue()
        self.thread = None
        self.stop = False

        self.outdate_ts = datetime.now()
        self.outdate_ts_lock = threading.Lock()

        self.collection_name = ""
        self.chat_memory_token_limit = 3000
        self.chat_memory = None

    def _send_text_data(self, ten: TenEnv, text: str, end_of_segment: bool):
        try:
            output_data = Data.create("text_data")
            output_data.set_property_string("text", text)
            output_data.set_property_bool("end_of_segment", end_of_segment)
            ten.send_data(output_data)
            logger.info("text [{}] end_of_segment {} sent".format(text, end_of_segment))
        except Exception as err:
            logger.info(
                "text [{}] end_of_segment {} send failed, err {}".format(
                    text, end_of_segment, err
                )
            )

    def on_start(self, ten: TenEnv) -> None:
        logger.info("on_start")

        greeting = None
        try:
            greeting = ten.get_property_string(PROPERTY_GREETING)
        except Exception as err:
            logger.warning(f"get {PROPERTY_GREETING} property failed, err: {err}")

        try:
            self.chat_memory_token_limit = ten.get_property_int(
                PROPERTY_CHAT_MEMORY_TOKEN_LIMIT
            )
        except Exception as err:
            logger.warning(
                f"get {PROPERTY_CHAT_MEMORY_TOKEN_LIMIT} property failed, err: {err}"
            )

        self.thread = threading.Thread(target=self.async_handle, args=[ten])
        self.thread.start()

        # enable chat memory
        from llama_index.core.storage.chat_store import SimpleChatStore
        from llama_index.core.memory import ChatMemoryBuffer
        self.chat_memory = ChatMemoryBuffer.from_defaults(
            token_limit=self.chat_memory_token_limit,
            chat_store=SimpleChatStore(),
        )

        # Send greeting if available
        if greeting is not None:
            self._send_text_data(ten, greeting, True)

        ten.on_start_done()

    def on_stop(self, ten: TenEnv) -> None:
        logger.info("on_stop")

        self.stop = True
        self.flush()
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        self.chat_memory = None

        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:

        cmd_name = cmd.get_name()
        logger.info("on_cmd {}".format(cmd_name))
        if cmd_name == "file_chunked":
            coll = cmd.get_property_string("collection")

            # only update selected collection if empty
            if len(self.collection_name) == 0:
                logger.info(
                    "collection for querying has been updated from {} to {}".format(
                        self.collection_name, coll
                    )
                )
                self.collection_name = coll
            else:
                logger.info(
                    "new collection {} incoming but won't change current collection_name {}".format(
                        coll, self.collection_name
                    )
                )

            # notify user
            file_chunked_text = "Your document has been processed. You can now start asking questions about your document. "
            # self._send_text_data(ten, file_chunked_text, True)
            self.queue.put((file_chunked_text, datetime.now(), TASK_TYPE_GREETING))
        elif cmd_name == "file_chunk":
            self.collection_name = ""  # clear current collection

            # notify user
            file_chunk_text = "Your document has been received. Please wait a moment while we process it for you.  "
            # self._send_text_data(ten, file_chunk_text, True)
            self.queue.put((file_chunk_text, datetime.now(), TASK_TYPE_GREETING))
        elif cmd_name == "update_querying_collection":
            coll = cmd.get_property_string("collection")
            logger.info(
                "collection for querying has been updated from {} to {}".format(
                    self.collection_name, coll
                )
            )
            self.collection_name = coll

            # notify user
            update_querying_collection_text = "Your document has been updated. "
            if len(self.collection_name) > 0:
                update_querying_collection_text += (
                    "You can now start asking questions about your document. "
                )
            # self._send_text_data(ten, update_querying_collection_text, True)
            self.queue.put(
                (update_querying_collection_text, datetime.now(), TASK_TYPE_GREETING)
            )

        elif cmd_name == "flush":
            self.flush()
            ten.send_cmd(Cmd.create("flush"), None)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "ok")
        ten.return_result(cmd_result, cmd)

    def on_data(self, ten: TenEnv, data: Data) -> None:
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
        self.queue.put((inputText, ts, TASK_TYPE_CHAT_REQUEST))

    def async_handle(self, ten: TenEnv):
        logger.info("async_handle started")
        while not self.stop:
            try:
                value = self.queue.get()
                if value is None:
                    break
                input_text, ts, task_type = value

                if ts < self.get_outdated_ts():
                    logger.info(
                        "text [{}] ts [{}] task_type [{}] dropped due to outdated".format(
                            input_text, ts, task_type
                        )
                    )
                    continue

                if task_type == TASK_TYPE_GREETING:
                    # send greeting text directly
                    self._send_text_data(ten, input_text, True)
                    continue

                logger.info("process input text [%s] ts [%s]", input_text, ts)

                # lazy import packages which requires long time to load
                from .llama_llm import LlamaLLM
                from .llama_retriever import LlamaRetriever

                # prepare chat engine
                chat_engine = None
                if len(self.collection_name) > 0:
                    from llama_index.core.chat_engine import ContextChatEngine
                    chat_engine = ContextChatEngine.from_defaults(
                        llm=LlamaLLM(ten=ten),
                        retriever=LlamaRetriever(ten=ten, coll=self.collection_name),
                        memory=self.chat_memory,
                        system_prompt=(
                            # "You are an expert Q&A system that is trusted around the world.\n"
                            "You are a voice assistant who talks in a conversational way and can chat with me like my friends. \n"
                            "I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. \n"
                            "Don’t talk like a robot, instead I would like you to talk like a real human with emotions. \n"
                            "I will use your answer for text-to-speech, so don’t return me any meaningless characters. \n"
                            "I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. \n"
                            "When giving me a list of options, express the options in a narrative way instead of bullet points.\n"
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
                    from llama_index.core.chat_engine import SimpleChatEngine
                    chat_engine = SimpleChatEngine.from_defaults(
                        llm=LlamaLLM(ten=ten),
                        system_prompt=(
                            "You are a voice assistant who talks in a conversational way and can chat with me like my friends. \n"
                            "I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. \n"
                            "Don’t talk like a robot, instead I would like you to talk like a real human with emotions. \n"
                            "I will use your answer for text-to-speech, so don’t return me any meaningless characters. \n"
                            "I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. \n"
                            "When giving me a list of options, express the options in a narrative way instead of bullet points.\n"
                        ),
                        memory=self.chat_memory,
                    )

                resp = chat_engine.stream_chat(input_text)
                for cur_token in resp.response_gen:
                    if self.stop:
                        break
                    if ts < self.get_outdated_ts():
                        logger.info(
                            "stream_chat coming responses dropped due to outdated for input text [%s] ts [%s] ",
                            input_text,
                            ts,
                        )
                        break
                    text = str(cur_token)

                    # send out
                    self._send_text_data(ten, text, False)

                # send out end_of_segment
                self._send_text_data(ten, "", True)
            except Exception as e:
                logger.exception(e)
        logger.info("async_handle stoped")

    def flush(self):
        with self.outdate_ts_lock:
            self.outdate_ts = datetime.now()

        while not self.queue.empty():
            self.queue.get()

    def get_outdated_ts(self):
        with self.outdate_ts_lock:
            return self.outdate_ts
