#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    Extension,
    TenEnv,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
)
from typing import List, Any
import queue
import json
from datetime import datetime
import threading
import re
import aisuite as ai

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"


class AISuiteLLMExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.history = []
        self.provider_config = {}
        self.api_key = ""
        self.model = ""
        self.prompt = ""
        self.max_tokens = 512
        self.max_history = 10
        self.stopped = False
        self.thread = None
        self.sentence_expr = re.compile(r".+?[,，.。!！?？:：]", re.DOTALL)

        self.outdate_ts = datetime.now()
        self.outdate_ts_lock = threading.Lock()

        self.queue = queue.Queue()
        self.mutex = threading.Lock()

        self.client = None

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
        with self.outdate_ts_lock:
            return self.outdate_ts > ts

    def get_outdate_ts(self) -> datetime:
        with self.outdate_ts_lock:
            return self.outdate_ts

    def complete_with_history(self, ten: TenEnv, ts: datetime.time, input_text: str):
        """
        Complete input_text querying with built-in chat history.
        """

        def callback(text: str, end_of_segment: bool):
            d = Data.create("text_data")
            d.set_property_string("text", text)
            d.set_property_bool("end_of_segment", end_of_segment)
            ten.send_data(d)

        messages = self.get_messages()
        messages.append({"role": "user", "content": input_text})
        total = self.stream_chat(ts, messages, callback)
        self.on_msg("user", input_text)
        if len(total) > 0:
            self.on_msg("assistant", total)

    def call_chat(self, ten: TenEnv, ts: datetime.time, cmd: Cmd):
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
                ten.log_info(
                    f"TTFS {int(curr_ttfs.total_seconds() * 1000)}ms, sentence {text} end_of_segment {end_of_segment}"
                )

            cmd_result = CmdResult.create(StatusCode.OK)
            cmd_result.set_property_string("text", text)
            if end_of_segment:
                cmd_result.set_is_final(True)  # end of streaming return
            else:
                cmd_result.set_is_final(False)  # keep streaming return
            ten.log_info(f"call_chat cmd return_result {cmd_result.to_json()}")
            ten.return_result(cmd_result, cmd)

        messages_str = cmd.get_property_string("messages")
        messages = json.loads(messages_str)
        stream = False
        try:
            stream = cmd.get_property_bool("stream")
        except Exception:
            ten.log_warn("stream property not found, default to False")

        if stream:
            self.stream_chat(ts, messages, callback)
        else:
            total = self.stream_chat(ts, messages, None)
            callback(total, True)  # callback once until full answer returned

    def stream_chat(self, ts: datetime.time, messages: List[Any], callback):
        ten = self.ten
        ten.log_info(f"before stream_chat call {messages} {ts}")

        if self.need_interrupt(ts):
            ten.log_warn("out of date, %s, %s", self.get_outdate_ts(), ts)
            return

        responses = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            max_tokens=self.max_tokens,
        )

        total = ""
        partial = ""
        for response in responses:
            if self.need_interrupt(ts):
                ten.log_warn("out of date, %s, %s", self.get_outdate_ts(), ts)
                partial = ""  # discard not sent
                break
            if len(response.choices) == 0:
                continue
            choice = response.choices[0]
            delta = choice.delta

            temp = delta.content if delta and delta.content else ""
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
                ten.log_warn(
                    f"request_id: {response.request_id}, status_code: {response.status_code}, error code: {response.code}, error message: {response.message}"
                )
                break

        # always send end_of_segment
        if callback is not None:
            callback(partial, True)
        ten.log_info(f"stream_chat full_answer {total}")
        return total

    def on_start(self, ten: TenEnv) -> None:
        ten.log_info("on_start")
        self.provider_config = ten.get_property_string("provider_config")
        self.model = ten.get_property_string("model")
        self.prompt = ten.get_property_string("prompt")
        self.max_history = ten.get_property_int("max_memory_length")
        self.max_tokens = ten.get_property_int("max_tokens")
        self.client = ai.Client(json.loads(self.provider_config))
        greeting = ten.get_property_string("greeting")

        if greeting:
            try:
                output_data = Data.create("text_data")
                output_data.set_property_string(
                    DATA_OUT_TEXT_DATA_PROPERTY_TEXT, greeting
                )
                output_data.set_property_bool(
                    DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True
                )
                ten.send_data(output_data)
                ten.log_info(f"greeting [{greeting}] sent")
            except Exception as e:
                ten.log_error(f"greeting [{greeting}] send failed, err: {e}")

        self.thread = threading.Thread(target=self.async_handle, args=[ten])
        self.thread.start()
        ten.on_start_done()

    def on_stop(self, ten: TenEnv) -> None:
        ten.log_info("on_stop")
        self.stopped = True
        self.flush()
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        ten.on_stop_done()

    def flush(self):
        with self.outdate_ts_lock:
            self.outdate_ts = datetime.now()

        while not self.queue.empty():
            self.queue.get()

    def on_data(self, ten: TenEnv, data: Data) -> None:
        ten.log_info("on_data")
        is_final = data.get_property_bool("is_final")
        if not is_final:
            ten.log_info("ignore non final")
            return

        input_text = data.get_property_string("text")
        if len(input_text) == 0:
            ten.log_info("ignore empty text")
            return

        ts = datetime.now()
        ten.log_info("on data %s, %s", input_text, ts)
        self.queue.put((input_text, ts))

    def async_handle(self, ten: TenEnv):
        while not self.stopped:
            try:
                value = self.queue.get()
                if value is None:
                    break
                chat_input, ts = value
                if self.need_interrupt(ts):
                    continue

                if isinstance(chat_input, str):
                    ten.log_info(f"fetched from queue {chat_input}")
                    self.complete_with_history(ten, ts, chat_input)
                else:
                    ten.log_info(f"fetched from queue {chat_input.get_name()}")
                    self.call_chat(ten, ts, chat_input)
            except Exception as e:
                ten.log_error(str(e))

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        ts = datetime.now()
        cmd_name = cmd.get_name()
        ten.log_info(f"on_cmd {cmd_name}, {ts}")

        if cmd_name == "flush":
            self.flush()
            cmd_out = Cmd.create("flush")
            ten.send_cmd(
                cmd_out,
                lambda ten, result: ten.log_info("send_cmd flush done"),
            )
        elif cmd_name == "call_chat":
            self.queue.put((cmd, ts))
            return  # cmd_result will be returned once it's processed
        else:
            ten.log_info(f"unknown cmd {cmd_name}")

        cmd_result = CmdResult.create(StatusCode.OK)
        ten.return_result(cmd_result, cmd)
