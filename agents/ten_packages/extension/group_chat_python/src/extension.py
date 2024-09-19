#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
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
from partialjson.json_parser import JSONParser
from datetime import datetime
import re
import threading
import queue
import re
from .log import logger
from .openai_chatgpt import OpenAIChatGPT, OpenAIChatGPTConfig

CMD_IN_FLUSH = "flush"
CMD_OUT_FLUSH = "flush"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_STREAM_ID = "stream_id"
DATA_IN_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"

PROPERTY_BASE_URL = "base_url"  # Optional
PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_MODEL = "model"  # Optional
PROPERTY_PROMPT = "prompt"  # Optional
PROPERTY_FREQUENCY_PENALTY = "frequency_penalty"  # Optional
PROPERTY_PRESENCE_PENALTY = "presence_penalty"  # Optional
PROPERTY_TEMPERATURE = "temperature"  # Optional
PROPERTY_TOP_P = "top_p"  # Optional
PROPERTY_MAX_TOKENS = "max_tokens"  # Optional
PROPERTY_CHARACTER = "character"  # Optional
PROPERTY_ENABLE_TOOLS = "enable_tools"  # Optional
PROPERTY_PROXY_URL = "proxy_url"  # Optional
PROPERTY_STREAM_ID = "stream_id"  # Optional
PROPERTY_MAX_MEMORY_LENGTH = "max_memory_length"  # Optional
PROPERTY_CHECKING_VISION_TEXT_ITEMS = "checking_vision_text_items"  # Optional

PUNCTUATION = r".+?[,，.。!！?？:：]"

def get_current_time():
    # Get the current time
    start_time = datetime.now()
    # Get the number of microseconds since the Unix epoch
    unix_microseconds = int(start_time.timestamp() * 1_000_000)
    return unix_microseconds

def is_punctuation(char):
    if char in [",", "，", ".", "。", "?", "？", "!", "！"]:
        return True
    return False


def parse_sentence(sentence, content):
    remain = ""
    found_punc = False

    for char in content:
        if not found_punc:
            sentence += char
        else:
            remain += char

        if not found_punc and is_punctuation(char):
            found_punc = True

    return sentence, remain, found_punc

class User:
    def __init__(self, uid:str) -> None:
        self.uid = uid
        self.role = "User_{}".format(uid) # For future rtm nick name mapping

class GroupChatExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)
        self.history = []
        self.max_memory_length = 16
        self.stream_id = 1234
        self.users = dict() # Only set in ten thread
        self.multi = False # Set in ten thread, read in self thread

        self.stopped = False
        self.thread = None
        self.sentence_expr = re.compile(r".+?[,，.。!！?？:：]", re.DOTALL)

        self.outdate_ts = get_current_time()
        self.outdate_ts_lock = threading.Lock()

        self.queue = queue.Queue()
        self.mutex = threading.Lock()

    def on_init(self, ten_env: TenEnv) -> None:
        logger.info("GroupChatExtension on_init")
        ten_env.on_init_done()

    def on_start(self, ten_env: TenEnv) -> None:
        logger.info("GroupChatExtension on_start")

        openai_chatgpt_config = OpenAIChatGPTConfig.default_config()

        try:
            base_url = ten_env.get_property_string(PROPERTY_BASE_URL)
            if base_url:
                openai_chatgpt_config.base_url = base_url
        except Exception as err:
            logger.info(f"GetProperty required {PROPERTY_BASE_URL} failed, err: {err}")

        try:
            api_key = ten_env.get_property_string(PROPERTY_API_KEY)
            openai_chatgpt_config.api_key = api_key
        except Exception as err:
            logger.info(f"GetProperty required {PROPERTY_API_KEY} failed, err: {err}")
            return

        try:
            model = ten_env.get_property_string(PROPERTY_MODEL)
            if model:
                openai_chatgpt_config.model = model
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_MODEL} error: {err}")

        try:
            prompt = ten_env.get_property_string(PROPERTY_PROMPT)
            if prompt:
                openai_chatgpt_config.prompt = prompt
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_PROMPT} error: {err}")

        try:
            frequency_penalty = ten_env.get_property_float(PROPERTY_FREQUENCY_PENALTY)
            openai_chatgpt_config.frequency_penalty = float(frequency_penalty)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_FREQUENCY_PENALTY} failed, err: {err}"
            )

        try:
            presence_penalty = ten_env.get_property_float(PROPERTY_PRESENCE_PENALTY)
            openai_chatgpt_config.presence_penalty = float(presence_penalty)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_PRESENCE_PENALTY} failed, err: {err}"
            )

        try:
            temperature = ten_env.get_property_float(PROPERTY_TEMPERATURE)
            openai_chatgpt_config.temperature = float(temperature)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_TEMPERATURE} failed, err: {err}"
            )

        try:
            top_p = ten_env.get_property_float(PROPERTY_TOP_P)
            openai_chatgpt_config.top_p = float(top_p)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_TOP_P} failed, err: {err}")

        try:
            max_tokens = ten_env.get_property_int(PROPERTY_MAX_TOKENS)
            if max_tokens > 0:
                openai_chatgpt_config.max_tokens = int(max_tokens)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_MAX_TOKENS} failed, err: {err}"
            )

        try:
            proxy_url = ten_env.get_property_string(PROPERTY_PROXY_URL)
            openai_chatgpt_config.proxy_url = proxy_url
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_PROXY_URL} failed, err: {err}")

        try:
            character = ten_env.get_property_string(PROPERTY_CHARACTER)
            openai_chatgpt_config.character = character
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_CHARACTER} failed, err: {err}")

        try:
            self.stream_id = ten_env.get_property_int(PROPERTY_STREAM_ID)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_STREAM_ID} failed, err: {err}"
            )

        try:
            prop_max_memory_length = ten_env.get_property_int(PROPERTY_MAX_MEMORY_LENGTH)
            if prop_max_memory_length > 0:
                self.max_memory_length = int(prop_max_memory_length)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_MAX_MEMORY_LENGTH} failed, err: {err}"
            )
        
        try:
            self.openai_chatgpt = OpenAIChatGPT(openai_chatgpt_config)
            logger.info(
                f"newOpenaiChatGPT succeed with max_tokens: {openai_chatgpt_config.max_tokens}, model: {openai_chatgpt_config.model}"
            )
        except Exception as err:
            logger.info(f"newOpenaiChatGPT failed, err: {err}")

        self.thread = threading.Thread(target=self.async_handle, args=[ten_env])
        self.thread.start()

        ten_env.on_start_done()
    
    def async_handle(self, ten_env: TenEnv) -> None:
        while not self.stopped:
            try:
                value = self.queue.get()
                if value is None:
                    logger.info("exit handle loop")
                    break
                ts, input, role = value
                if self.need_interrupt(ts):
                    continue

                logger.info("fetched from queue {} {}\t{}:{}".format(self.multi, ts, input, role))
                if self.multi:
                    self.on_text(ten_env, ts, input, role, True)
                else:
                    self.on_text(ten_env, ts, input, role, False)
            except Exception as e:
                logger.exception("Failed to chat")

    def send_data(self, ten_env: TenEnv, sentence: str, end_of_segment: bool, stream_id: int):
        try:
            d = Data.create("text_data")
            d.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, sentence)
            d.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, end_of_segment)
            d.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_TEXT_IS_FINAL, True)
            d.set_property_int(DATA_IN_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
            ten_env.send_data(d)
            logger.info(
                f"{'end of segment ' if end_of_segment else ''}sent sentence [{sentence}]"
            )
        except Exception as err:
            logger.info(
                f"send sentence [{sentence}] failed, err: {err}"
            )

    # return new full content, content, buffer and sent
    def streaming_process(self, ten_env: TenEnv, delta:str, full_content:str, buffer):
        sent = False
        content = ""

        full_content += delta
        if buffer is not None:
            buffer += delta
        parser = JSONParser(strict=False)
        try:
            sj = parser.parse(full_content)
            # logger.info("partial: {}".format(sj))

            if sj.get("need_response") is None:
                logger.info("no response received: {}".format(full_content))
                return full_content, "", buffer, False
            elif not sj.get("need_response"):
                logger.info("no need to response: {}".format(full_content))
                return full_content, "", buffer, False
            elif buffer is None:
                # Set only when buffer is None
                buffer = sj.get("content")
            content = sj.get("content")
        except Exception as err:
            logger.exception("Failed to load partial: full: {} buffer: {}".format(full_content, buffer))
            return full_content, "", buffer, False
        
        if not buffer:
            return full_content, "", None, False
        
        match = re.search(PUNCTUATION, buffer)
        while match:
            sentence = match.group()
            buffer = buffer[len(sentence):]
            sent = True
            self.send_data(ten_env, sentence, False, self.stream_id)
            logger.info("after regex content: full: {} buffer: {} sentence {}".format(full_content, buffer, sentence))
            match = re.search(PUNCTUATION, buffer)

        return full_content, content, buffer, sent

    def on_text(self, ten_env: TenEnv, ts:int, input_text:str, role:str, multi:bool) -> None:
        messages = self.get_memories()
        messages.append({"role": "user", "content": f"{role}: {input_text}"})
        # logger.debug("before llm call {} {}".format(messages, ts))

        if self.need_interrupt(ts):
            logger.warning("out of date, %s, %s", self.outdate_ts, ts)
            return
        
        full_content = ""
        interrupted = False
        first_sentence_sent = False
        content = ""
        buffer = None
        # lexer = streamingjson.Lexer()
        
        try:
            if self.multi:
                resp = self.openai_chatgpt.get_chat_completions_group_stream(messages)
            else:
                resp = self.openai_chatgpt.get_chat_completions_stream(messages)
            if resp is None:
                logger.error("get_chat_completions_stream Response is None: {} {}".format(messages, ts))
                return
            for c in resp:
                delta = ""
                if ts < self.outdate_ts:
                    interrupted = True
                    logger.info("recv interrupt and flushing for input text: {}, startTs: {}, outdateTs: {}".format(messages, ts, self.outdate_ts))
                    break

                if len(c.choices) > 0:
                    if c.choices[0].delta.content is not None:
                        delta = c.choices[0].delta.content
                else:
                    continue

                full_content, content, buffer, sent = self.streaming_process(ten_env, delta, full_content, buffer)
                if sent and not first_sentence_sent:
                    first_sentence_sent = True
                    logger.info(
                        f"recv for input text: [{input_text}] first sentence sent, first_sentence_latency {get_current_time() - ts}ms"
                    )
            
            full_content, content, buffer, sent = self.streaming_process(ten_env, "", full_content, buffer)
            logger.info("content: full: {}, content: {}, buffer: {}".format(full_content, content, buffer))
            self.append_memory("user", f"{role}: {input_text}", False)
            if content:
                self.append_memory("assistant", content, interrupted)
            self.send_data(ten_env, "", True, self.stream_id)
        except Exception as err:
            logger.exception("Failed to call llm: {} {}".format(messages, ts))

    def append_memory(self, role:str, content:str, interrupted:bool):
        if interrupted:
            content += "[interrupted]"
        self.mutex.acquire()
        try:
            self.history.append({"role": role, "content": content})
            if len(self.history) > self.max_memory_length:
                self.history = self.history[1:]
        finally:
            self.mutex.release()

    def get_memories(self):
        messages = []
        self.mutex.acquire()
        try:
            for h in self.history:
                messages.append(h)
        finally:
            self.mutex.release()
        return messages

    def on_stop(self, ten_env: TenEnv) -> None:
        logger.info("GroupChatExtension on_stop")
        self.stopped = True
        self.flush()
        self.queue.put(None)
        if self.thread is not None:
            self.thread.join()
            self.thread = None
        
        ten_env.on_stop_done()

    def flush(self) -> None:
        logger.info("GroupChatExtension flush")
        with self.outdate_ts_lock:
            self.outdate_ts = get_current_time()

        while not self.queue.empty():
            self.queue.get()
    
    def need_interrupt(self, ts:int) -> None:
        with self.outdate_ts_lock:
            return self.outdate_ts > ts

    def on_deinit(self, ten_env: TenEnv) -> None:
        logger.info("GroupChatExtension on_deinit")
        ten_env.on_deinit_done()

    def on_cmd(self, ten_env: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd name {}".format(cmd_name))

        if cmd_name == "on_user_joined":
            try:
                struid = cmd.get_property_string("remote_user_id")
                uid = int(struid)
                self.users[uid] = User(uid)
                if len(self.users) > 1:
                    self.multi = True
            except Exception as err:
                logger.exception("Failed to get stream id")
        elif cmd_name == "on_user_left":
            try:
                struid = cmd.get_property_string("remote_user_id")
                uid = int(struid)
                del self.users[uid]
                if len(self.users) <= 1:
                    self.multi = False
            except Exception as err:
                logger.exception("Failed to get stream id")
        elif cmd_name == CMD_IN_FLUSH:
            self.flush()
            cmd_out = Cmd.create(CMD_OUT_FLUSH)
            ten_env.send_cmd(cmd_out, None)
            logger.info(f"GroupChatExtension on_cmd sent flush")

        cmd_result = CmdResult.create(StatusCode.OK)
        ten_env.return_result(cmd_result, cmd)

    def on_data(self, ten_env: TenEnv, data: Data) -> None:
        logger.info(f"GroupChatExtension on_data")

        # Assume 'data' is an object from which we can get properties
        try:
            is_final = data.get_property_bool(DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL)
            if not is_final:
                logger.info("ignore non-final input")
                return
        except Exception as err:
            logger.info(
                f"OnData GetProperty {DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL} failed, err: {err}"
            )
            return

        # Get input text
        try:
            input_text = data.get_property_string(DATA_IN_TEXT_DATA_PROPERTY_TEXT)
            if not input_text:
                logger.info("ignore empty text")
                return
            logger.info(f"OnData input text: [{input_text}]")
        except Exception as err:
            logger.info(
                f"OnData GetProperty {DATA_IN_TEXT_DATA_PROPERTY_TEXT} failed, err: {err}"
            )
            return
        
        # Get input text
        try:
            stream_id = data.get_property_int(DATA_IN_TEXT_DATA_PROPERTY_STREAM_ID)
            if not stream_id:
                logger.warning("ignore empty stream_id")
                return
        except Exception as err:
            logger.info(
                f"OnData GetProperty {DATA_IN_TEXT_DATA_PROPERTY_STREAM_ID} failed, err: {err}"
            )
            return


        u = self.users.get(stream_id)
        if u is None:
            logger.warning("ignore unknown stream_id {}".format(stream_id))
            return
        ts = get_current_time()
        self.queue.put((ts, input_text, u.role))

    def on_audio_frame(self, ten_env: TenEnv, audio_frame: AudioFrame) -> None:
        # TODO: process pcm frame
        pass

    def on_video_frame(self, ten_env: TenEnv, video_frame: VideoFrame) -> None:
        # TODO: process image frame
        pass
