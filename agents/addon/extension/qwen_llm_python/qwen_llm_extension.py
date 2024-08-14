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
from typing import List, Any
import dashscope
import queue
import json
from datetime import datetime
import threading
import re
from http import HTTPStatus
from .log import logger


class QWenLLMExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.history = []
        self.api_key = ""
        self.model = ""
        self.prompt = ""
        self.max_history = 10
        self.stopped = False
        self.thread = None
        self.outdate_ts = datetime.now()
        self.sentence_expr = re.compile(r".+?[,，.。!！?？:：]", re.DOTALL)

        self.queue = queue.Queue()
        self.mutex = threading.Lock()

    def on_msg(self, role: str, content: str) -> None:
        self.mutex.acquire()
        try:
            self.history.append({"role": role, "content": content})
            if len(self.history) > self.max_history:
                self.history = self.history[1:]
        finally:
            self.mutex.release()

    def get_messages(self) -> List[Any]:
        messages = []
        if len(self.prompt) > 0:
            messages.append({"role": "system", "content": self.prompt})
        self.mutex.acquire()
        try:
            for h in self.history:
                messages.append(h)
        finally:
            self.mutex.release()
        return messages

    def need_interrupt(self, ts: datetime.time) -> bool:
        return self.outdate_ts > ts and (self.outdate_ts - ts).total_seconds() > 1

    def complete_with_history(self, rte: RteEnv, ts: datetime.time, input_text: str):
        """
        Complete input_text querying with built-in chat history.
        """

        def callback(text: str, end_of_segment: bool):
            d = Data.create("text_data")
            d.set_property_string("text", text)
            d.set_property_bool("end_of_segment", end_of_segment)
            rte.send_data(d)

        messages = self.get_messages()
        messages.append({"role": "user", "content": input_text})
        total = self.stream_chat(ts, messages, callback)
        self.on_msg("user", input_text)
        if len(total) > 0:
            self.on_msg("assistant", total)

    def call_chat(self, rte: RteEnv, ts: datetime.time, cmd: Cmd):
        """
        Respond to call_chat cmd and return results in streaming.
        The incoming 'messages' will contains all the system prompt, chat history and question.
        """

        start_time = datetime.now()
        curr_ttfs = None  # time to first sentence

        def callback(text: str, end_of_segment: bool):
            nonlocal curr_ttfs
            if curr_ttfs is None:
                curr_ttfs = datetime.now() - start_time
                logger.info(
                    "TTFS {}ms, sentence {} end_of_segment {}".format(
                        int(curr_ttfs.total_seconds() * 1000), text, end_of_segment
                    )
                )

            cmd_result = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_string("text", text)
            if end_of_segment:
                cmd_result.set_is_final(True)  # end of streaming return
            else:
                cmd_result.set_is_final(False)  # keep streaming return
            logger.info("call_chat cmd return_result {}".format(cmd_result.to_json()))
            rte.return_result(cmd_result, cmd)

        messages_str = cmd.get_property_string("messages")
        messages = json.loads(messages_str)
        stream = False
        try:
            stream = cmd.get_property_bool("stream")
        except Exception as e:
            logger.warning("stream property not found, default to False")

        if stream:
            self.stream_chat(ts, messages, callback)
        else:
            total = self.stream_chat(ts, messages, None)
            callback(total, True)  # callback once until full answer returned

    def stream_chat(self, ts: datetime.time, messages: List[Any], callback):
        logger.info("before stream_chat call {} {}".format(messages, ts))

        if self.need_interrupt(ts):
            logger.warning("out of date, %s, %s", self.outdate_ts, ts)
            return

        responses = dashscope.Generation.call(
            self.model,
            messages=messages,
            result_format="message",  # set the result to be "message"  format.
            stream=True,  # set streaming output
            incremental_output=True,  # get streaming output incrementally
        )

        total = ""
        partial = ""
        for response in responses:
            if self.need_interrupt(ts):
                logger.warning("out of date, %s, %s", self.outdate_ts, ts)
                partial = ""  # discard not sent
                break
            if response.status_code == HTTPStatus.OK:
                temp = response.output.choices[0]["message"]["content"]
                if len(temp) == 0:
                    continue
                partial += temp
                total += temp

                m = self.sentence_expr.match(partial)
                if m is not None:
                    sentence = m.group(0)
                    partial = partial[m.end(0) :]
                    if callback is not None:
                        callback(sentence, False)

            else:
                logger.warning(
                    "request_id: {}, status_code: {}, error code: {}, error message: {}".format(
                        response.request_id,
                        response.status_code,
                        response.code,
                        response.message,
                    )
                )
                break

        # always send end_of_segment
        if callback is not None:
            callback(partial, True)
        logger.info("stream_chat full_answer {}".format(total))
        return total

    def on_start(self, rte: RteEnv) -> None:
        logger.info("on_start")
        self.api_key = rte.get_property_string("api_key")
        self.model = rte.get_property_string("model")
        self.prompt = rte.get_property_string("prompt")
        self.max_history = rte.get_property_int("max_memory_length")

        dashscope.api_key = self.api_key
        self.thread = threading.Thread(target=self.async_handle, args=[rte])
        self.thread.start()
        rte.on_start_done()

    def on_stop(self, rte: RteEnv) -> None:
        logger.info("on_stop")
        self.stopped = True
        self.flush()
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        rte.on_stop_done()

    def flush(self):
        self.outdate_ts = datetime.now()
        while not self.queue.empty():
            self.queue.get()

    def on_data(self, rte: RteEnv, data: Data) -> None:
        logger.info("on_data")
        is_final = data.get_property_bool("is_final")
        if not is_final:
            logger.info("ignore non final")
            return

        input_text = data.get_property_string("text")
        if len(input_text) == 0:
            logger.info("ignore empty text")
            return

        ts = datetime.now()
        logger.info("on data %s, %s", input_text, ts)
        self.queue.put((input_text, ts))

    def async_handle(self, rte: RteEnv):
        while not self.stopped:
            try:
                value = self.queue.get()
                if value is None:
                    break
                input, ts = value
                if self.need_interrupt(ts):
                    continue

                if isinstance(input, str):
                    logger.info("fetched from queue {}".format(input))
                    self.complete_with_history(rte, ts, input)
                else:
                    logger.info("fetched from queue {}".format(input.get_name()))
                    self.call_chat(rte, ts, input)
            except Exception as e:
                logger.exception(e)

    def on_cmd(self, rte: RteEnv, cmd: Cmd) -> None:
        ts = datetime.now()
        cmd_name = cmd.get_name()
        logger.info("on_cmd {}, {}".format(cmd_name, ts))

        if cmd_name == "flush":
            self.flush()
            cmd_out = Cmd.create("flush")
            rte.send_cmd(
                cmd_out,
                lambda rte, result: logger.info("send_cmd flush done"),
            )
        elif cmd_name == "call_chat":
            self.queue.put((cmd, ts))
            return  # cmd_result will be returned once it's processed
        else:
            logger.info("unknown cmd {}".format(cmd_name))

        cmd_result = CmdResult.create(StatusCode.OK)
        rte.return_result(cmd_result, cmd)
