#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import time
from datetime import datetime
from queue import Queue
from threading import Thread, Lock

from cozepy import ChatEventType, Coze, Message, TokenAuth, SyncHTTPClient, CozeAPIError

from ten import (
    AudioFrame,
    VideoFrame,
    Extension,
    TenEnv,
    Cmd,
    StatusCode,
    CmdResult,
    Data,
)

PROPERTY_TOKEN = "token"
PROPERTY_BOT_ID = "bot_id"
PROPERTY_BASE_URL = "base_url"
PROPERTY_ENABLE_STORAGE = "enable_storage"
PROPERTY_USER_ID = "user_id"
PROPERTY_PROMPT = "prompt"

DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"

def is_punctuation(char):
    if char in [",", "，", ".", "。", "?", "？", "!", "！"]:
        return True
    return False

def parse_sentences(sentence_fragment, content):
    sentences = []
    current_sentence = sentence_fragment
    for char in content:
        current_sentence += char
        if is_punctuation(char):
            # Check if the current sentence contains non-punctuation characters
            stripped_sentence = current_sentence
            if any(c.isalnum() for c in stripped_sentence):
                sentences.append(stripped_sentence)
            current_sentence = ""  # Reset for the next sentence

    remain = current_sentence  # Any remaining characters form the incomplete sentence
    return sentences, remain
class CozeExtension(Extension):
    token:str = ""
    bot_id:str = ""
    base_url:str = "https://api.coze.com"
    user_id:str = "TenAgent"
    prompt:str = ""
    sentence_fragment:str = ""
    enable_storage: bool = False
    queue:Queue = Queue()
    outdate_ts = datetime.now()
    ten_env:TenEnv = None
    coze:Coze = None
    mtx:Lock = Lock()
    http:SyncHTTPClient = None
    stopped:bool = False
    thread:Thread = None

    def on_init(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_start")

        try:
            self.token = ten_env.get_property_string(PROPERTY_TOKEN)
        except Exception as err:
            ten_env.log_error(
                f"GetProperty optional {PROPERTY_TOKEN} failed, err: {err}"
            )
            return
    
        try:
            self.bot_id = ten_env.get_property_string(PROPERTY_BOT_ID)
        except Exception as err:
            ten_env.log_error(
                f"GetProperty optional {PROPERTY_BOT_ID} failed, err: {err}"
            )
            return
        
        try:
            self.base_url = ten_env.get_property_string(PROPERTY_BASE_URL)
        except Exception as err:
            ten_env.log_error(
                f"GetProperty optional {PROPERTY_BASE_URL} failed, err: {err}"
            )
        
        try:
            self.enable_storage = ten_env.get_property_bool(PROPERTY_ENABLE_STORAGE)
        except Exception as err:
            ten_env.log_error(
                f"GetProperty optional {PROPERTY_ENABLE_STORAGE} failed, err: {err}"
            )

        try:
            self.user_id = ten_env.get_property_string(PROPERTY_USER_ID)
        except Exception as err:
            ten_env.log_error(
                f"GetProperty optional {PROPERTY_USER_ID} failed, err: {err}"
            )
        
        try:
            self.prompt = ten_env.get_property_string(PROPERTY_PROMPT)
        except Exception as err:
            ten_env.log_error(
                f"GetProperty optional {PROPERTY_PROMPT} failed, err: {err}"
            )

        self.coze = Coze(auth=TokenAuth(token=self.token), base_url=self.base_url)

        messages = []
        if self.prompt:
            messages=[
                Message.build_user_question_text(self.prompt)
            ]

        self.conversation = self.coze.conversations.create(messages=messages)
        ten_env.log_info(f"get conversation {self.conversation.id}")

        self.ten_env = ten_env
        self.thread = Thread(target=self._async_loop)
        self.thread.start()

        ten_env.on_start_done()

    def on_stop(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_stop")

        self._flush()
        self.queue.put(None)
        self.stopped = True
        self.thread.join()

        ten_env.on_stop_done()

    def on_deinit(self, ten_env: TenEnv) -> None:
        ten_env.log_debug("on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        ten_env.log_debug("on_cmd name {}".format(cmd_name))

        if cmd_name == "flush":
            self._flush()
            cmd_out = Cmd.create("flush")
            ten_env.send_cmd(
                cmd_out,
                lambda ten, result: ten_env.log_info("send_cmd flush done"),
            )

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        data_name = data.get_name()
        ten_env.log_debug("on_data name {}".format(data_name))

        is_final = False
        input_text = ""
        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
        except Exception as err:
            ten_env.log_info(
                f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL} failed, err: {err}"
            )
        
        try:
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
        except Exception as err:
            ten_env.log_info(
                f"GetProperty optional {DATA_IN_TEXT_DATA_PROPERTY_TEXT} failed, err: {err}"
            )

        if not is_final:
            ten_env.log_info("ignore non-final input")
            return
        if not input_text:
            ten_env.log_info("ignore empty text")
            return

        ten_env.log_info(f"OnData input text: [{input_text}]")

        ts = datetime.now()
        # Start an asynchronous task for handling chat completion
        self.queue.put((input_text, ts))

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        pass

    def _async_loop(self) -> None:
        self.ten_env.log_info("start async loop")
        while not self.stopped:
            try:
                value = self.queue.get()
                if value is None:
                    self.ten_env.log_info("async loop exit")
                    break
                input, ts = value
                if self._need_interrrupt(ts):
                    continue

                self._chat(input, ts)
            except Exception as e:
                self.ten_env.log_error(f"Failed to handle {e}")

    def _need_interrrupt(self, ts:datetime) -> bool:
        return self.outdate_ts > ts
    
    def _chat(self, input:str, ts:datetime) -> None:
        with self.mtx:
            self.http = SyncHTTPClient()
        coze = Coze(auth=TokenAuth(token=self.token), base_url=self.base_url, http_client=self.http)
        
        try:
            for event in coze.chat.stream(
                bot_id=self.bot_id,
                user_id=self.user_id,
                additional_messages=[
                    Message.build_user_question_text(input),
                ],
                conversation_id=self.conversation.id,
            ):
                if self._need_interrrupt(ts):
                    self.ten_env.log_info("interupted")
                    break
                
                self.ten_env.log_info(f"get result {event}")
                if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                    sentences, self.sentence_fragment = parse_sentences(
                        self.sentence_fragment, event.message.content)
                    for s in sentences:
                        self._send_text(s)
        except CozeAPIError as e:
            self.ten_env.log_error(f"failed to chat with api err {e}")
            if e.code == 4016:
                time.sleep(0.05)
                self._chat(input, ts)
            else:
                raise

    
    def _send_text(self, text:str) -> None:
        data = Data.create("text_data")
        data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text)
        data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, True)
        self.ten_env.send_data(data)

    def _flush(self):
        self.outdate_ts = datetime.now()

        while not self.queue.empty():
            self.queue.get()
        
        with self.mtx:
            if self.http:
                self.http.close()