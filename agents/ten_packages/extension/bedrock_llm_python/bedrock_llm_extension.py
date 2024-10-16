
import json
import copy

from datetime import datetime
from threading import Thread
from queue import Queue
from threading import Thread
from typing import List, Any, AnyStr
from base64 import b64decode

from ten import (
    Addon,
    Extension,
    register_addon_as_extension,
    TenEnv,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
)
from .log import logger
from .bedrock_llm import BedrockLLM, BedrockLLMConfig


CMD_IN_FLUSH = "flush"
CMD_OUT_FLUSH = "flush"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"

CMD_IN_CHAT_COMPLETION = "chat_completion"

PROPERTY_REGION = "region"  # Optional
PROPERTY_ACCESS_KEY = "access_key"  # Optional
PROPERTY_SECRET_KEY = "secret_key"  # Optional
PROPERTY_MODEL = "model"  # Optional
PROPERTY_PROMPT = "prompt"  # Optional
PROPERTY_TEMPERATURE = "temperature"  # Optional
PROPERTY_TOP_P = "top_p"  # Optional
PROPERTY_MAX_TOKENS = "max_tokens"  # Optional
PROPERTY_GREETING = "greeting"  # Optional
PROPERTY_MAX_MEMORY_LENGTH = "max_memory_length"  # Optional


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


class BedrockLLMExtension(Extension):
    memory = []
    max_memory_length = 10
    outdate_ts = 0
    bedrock_llm = None
    greeting = ""

    stopped: bool = False
    cmd_queue = Queue()
    thread: Thread = None
    ten_env: TenEnv = None

    def on_start(self, ten: TenEnv) -> None:
        logger.info("BedrockLLMExtension on_start")
        # Prepare configuration
        self.ten_env = ten
        bedrock_llm_config = BedrockLLMConfig.default_config()

        for optional_str_param in [
            PROPERTY_REGION,
            PROPERTY_ACCESS_KEY,
            PROPERTY_SECRET_KEY,
            PROPERTY_MODEL,
            PROPERTY_PROMPT,
        ]:
            try:
                value = ten.get_property_string(optional_str_param).strip()
                if value:
                    bedrock_llm_config.__setattr__(optional_str_param, value)
            except Exception as err:
                logger.debug(
                    f"GetProperty optional {optional_str_param} failed, err: {err}. Using default value: {bedrock_llm_config.__getattribute__(optional_str_param)}"
                )

        for optional_float_param in [PROPERTY_TEMPERATURE, PROPERTY_TOP_P]:
            try:
                value = ten.get_property_float(optional_float_param)
                if value:
                    bedrock_llm_config.__setattr__(optional_float_param, value)
            except Exception as err:
                logger.debug(
                    f"GetProperty optional {optional_float_param} failed, err: {err}. Using default value: {bedrock_llm_config.__getattribute__(optional_float_param)}"
                )

        try:
            max_tokens = ten.get_property_int(PROPERTY_MAX_TOKENS)
            if max_tokens > 0:
                bedrock_llm_config.max_tokens = int(max_tokens)
        except Exception as err:
            logger.debug(
                f"GetProperty optional {PROPERTY_MAX_TOKENS} failed, err: {err}. Using default value: {bedrock_llm_config.max_tokens}"
            )

        try:
            self.greeting = ten.get_property_string(PROPERTY_GREETING)
        except Exception as err:
            logger.debug(
                f"GetProperty optional {PROPERTY_GREETING} failed, err: {err}."
            )

        try:
            prop_max_memory_length = ten.get_property_int(PROPERTY_MAX_MEMORY_LENGTH)
            if prop_max_memory_length > 0:
                self.max_memory_length = int(prop_max_memory_length)
        except Exception as err:
            logger.debug(
                f"GetProperty optional {PROPERTY_MAX_MEMORY_LENGTH} failed, err: {err}."
            )

        # Create bedrockLLM instance
        try:
            self.bedrock_llm = BedrockLLM(bedrock_llm_config)
            logger.info(
                f"newBedrockLLM succeed with max_tokens: {bedrock_llm_config.max_tokens}, model: {bedrock_llm_config.model}"
            )
        except Exception as err:
            logger.exception(f"newBedrockLLM failed, err: {err}")

        self.thread = Thread(target=self.loop)
        self.thread.start()

        # Send greeting if available
        if self.greeting:
            try:
                output_data = Data.create("text_data")
                output_data.set_property_string(
                    DATA_OUT_TEXT_DATA_PROPERTY_TEXT, self.greeting
                )
                output_data.set_property_bool(
                    DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True
                )
                ten.send_data(output_data)
                logger.info(f"greeting [{self.greeting}] sent")
            except Exception as err:
                logger.info(f"greeting [{self.greeting}] send failed, err: {err}")
        ten.on_start_done()

    def on_stop(self, ten: TenEnv) -> None:
        logger.info("BedrockLLMExtension on_stop")
        self.stopped = True
        self.cmd_queue.put(None)
        self.thread.join()
        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        logger.info("BedrockLLMExtension on_cmd")
        cmd_json = cmd.to_json()
        logger.info("BedrockLLMExtension on_cmd json: " + cmd_json)

        cmd_name = cmd.get_name()

        if cmd_name == CMD_IN_FLUSH:
            self.outdate_ts = get_current_time()
            cmd_out = Cmd.create(CMD_OUT_FLUSH)
            ten.send_cmd(cmd_out, None)
            logger.info(f"BedrockLLMExtension on_cmd sent flush")
        elif cmd_name == CMD_IN_CHAT_COMPLETION:
            m_str = cmd.get_property_string("messages")
            messages = json.loads(m_str)
            stream = False
            is_json = False
            try:
                stream = cmd.get_property_bool("stream")
            except:
                pass
            
            try:
                is_json = cmd.get_property_bool("json")
            except:
                pass
            
            self.cmd_queue.put((messages, stream, is_json, cmd))
            return
        else:
            logger.info(f"BedrockLLMExtension on_cmd unknown cmd: {cmd_name}")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            cmd_result.set_property_string("detail", "unknown cmd")
            ten.return_result(cmd_result, cmd)
            return

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        ten.return_result(cmd_result, cmd)

    def on_data(self, ten: TenEnv, data: Data) -> None:
        """
        on_data receives data from ten graph.
        current suppotend data:
          - name: text_data
            example:
            {name: text_data, properties: {text: "hello"}
        """
        logger.info(f"BedrockLLMExtension on_data")

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

        # Prepare memory. A conversation must alternate between user and assistant roles
        while len(self.memory):
            if len(self.memory) > self.max_memory_length:
                logger.debug(
                    f"pop out first message, reason: memory length limit: `{self.memory[0]}`"
                )
                self.memory.pop(0)
            elif self.memory[0]["role"] == "assistant":
                logger.debug(
                    f"pop out first message, reason: messages can not start with assistant: `{self.memory[0]}`"
                )
                self.memory.pop(0)
            else:
                break

        if len(self.memory) and self.memory[-1]["role"] == "user":
            # if last user input got empty response, append current user input.
            logger.debug(
                f"found last message with role `user`, will append this input into last user input"
            )
            self.memory[-1]["content"].append({"text": input_text})
        else:
            self.memory.append({"role": "user", "content": [{"text": input_text}]})

        def converse_stream_worker(start_time, input_text, memory):
            try:
                logger.info(
                    f"GetConverseStream for input text: [{input_text}] memory: {memory}"
                )

                # Get result from Bedrock
                resp = self.bedrock_llm.get_converse_stream(memory)
                if resp is None or resp.get("stream") is None:
                    logger.info(
                        f"GetConverseStream for input text: [{input_text}] failed"
                    )
                    return

                stream = resp.get("stream")
                sentence = ""
                full_content = ""
                first_sentence_sent = False

                for event in stream:
                    # allow 100ms buffer time, in case interruptor's flush cmd comes just after on_data event
                    if (start_time + 100_000) < self.outdate_ts:
                        logger.info(
                            f"GetConverseStream recv interrupt and flushing for input text: [{input_text}], startTs: {start_time}, outdateTs: {self.outdate_ts}, delta > 100ms"
                        )
                        break

                    if "contentBlockDelta" in event:
                        delta_types = event["contentBlockDelta"]["delta"].keys()
                        # ignore other types of content: e.g toolUse
                        if "text" in delta_types:
                            content = event["contentBlockDelta"]["delta"]["text"]
                    elif (
                        "internalServerException" in event
                        or "modelStreamErrorException" in event
                        or "throttlingException" in event
                        or "validationException" in event
                    ):
                        logger.error(f"GetConverseStream Error occured: {event}")
                        break
                    else:
                        # ingore other events
                        continue

                    full_content += content

                    while True:
                        sentence, content, sentence_is_final = parse_sentence(
                            sentence, content
                        )
                        if not sentence or not sentence_is_final:
                            logger.info(f"sentence [{sentence}] is empty or not final")
                            break
                        logger.info(
                            f"GetConverseStream recv for input text: [{input_text}] got sentence: [{sentence}]"
                        )

                        # send sentence
                        try:
                            output_data = Data.create("text_data")
                            output_data.set_property_string(
                                DATA_OUT_TEXT_DATA_PROPERTY_TEXT, sentence
                            )
                            output_data.set_property_bool(
                                DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, False
                            )
                            ten.send_data(output_data)
                            logger.info(
                                f"GetConverseStream recv for input text: [{input_text}] sent sentence [{sentence}]"
                            )
                        except Exception as err:
                            logger.info(
                                f"GetConverseStream recv for input text: [{input_text}] send sentence [{sentence}] failed, err: {err}"
                            )
                            break

                        sentence = ""
                        if not first_sentence_sent:
                            first_sentence_sent = True
                            logger.info(
                                f"GetConverseStream recv for input text: [{input_text}] first sentence sent, first_sentence_latency {get_current_time() - start_time}ms"
                            )

                if len(full_content.strip()):
                    # remember response as assistant content in memory
                    if memory and memory[-1]["role"] == "assistant":
                        memory[-1]["content"].append({"text": full_content})
                    else:
                        memory.append(
                            {"role": "assistant", "content": [{"text": full_content}]}
                        )
                else:
                    # can not put empty model response into memory
                    logger.error(
                        f"GetConverseStream recv for input text: [{input_text}] failed: empty response [{full_content}]"
                    )
                    return

                # send end of segment
                try:
                    output_data = Data.create("text_data")
                    output_data.set_property_string(
                        DATA_OUT_TEXT_DATA_PROPERTY_TEXT, sentence
                    )
                    output_data.set_property_bool(
                        DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True
                    )
                    ten.send_data(output_data)
                    logger.info(
                        f"GetConverseStream for input text: [{input_text}] end of segment with sentence [{sentence}] sent"
                    )
                except Exception as err:
                    logger.info(
                        f"GetConverseStream for input text: [{input_text}] end of segment with sentence [{sentence}] send failed, err: {err}"
                    )

            except Exception as e:
                logger.info(
                    f"GetConverseStream for input text: [{input_text}] failed, err: {e}"
                )

        # Start thread to request and read responses from OpenAI
        start_time = get_current_time()
        thread = Thread(
            target=converse_stream_worker, args=(start_time, input_text, self.memory)
        )
        thread.start()
        logger.info(f"BedrockLLMExtension on_data end")

    def loop(self):
        logger.info(f"starting loop {self.stopped}")
        while not self.stopped:
            c = self.cmd_queue.get()
            if c is None:
                break
            
            try:
                messages, stream, is_json, cmd = c
                try:
                    messages = self._convert_messages(messages)
                    logger.info(f"after convert {messages}")
                    resp = self.bedrock_llm.chat_completion_cmd(messages=messages, stream=stream, is_json=is_json)
                    if not stream:
                        output_message = resp['output']['message']
                        cmd_result = CmdResult.create(StatusCode.OK)
                        cmd_result.set_property_string("response", output_message)
                        self.ten_env.return_result(cmd_result, cmd)
                    else:
                        stream = resp.get("stream")
                        status_code = StatusCode.OK
                        for event in stream:
                            if "contentBlockDelta" in event:
                                delta_types = event["contentBlockDelta"]["delta"].keys()
                                # ignore other types of content: e.g toolUse
                                if "text" in delta_types:
                                    content = event["contentBlockDelta"]["delta"]["text"]
                                    cmd_result = CmdResult.create(StatusCode.OK)
                                    cmd_result.set_property_string("response", content)
                                    cmd_result.set_is_final(False)
                                    self.ten_env.return_result(cmd_result, cmd)
                            elif (
                                "internalServerException" in event
                                or "modelStreamErrorException" in event
                                or "throttlingException" in event
                                or "validationException" in event
                            ):
                                logger.error(f"GetConverseStream Error occured: {event}")
                                status_code = StatusCode.ERROR
                                break
                            else:
                                # ingore other events
                                continue
                        
                        cmd_result = CmdResult.create(status_code)
                        cmd_result.set_property_string("response", "")
                        cmd_result.set_is_final(True)
                        self.ten_env.return_result(cmd_result, cmd)
                except:
                    logger.exception("Failed to handle queue")
            except:
                logger.exception("failed")
        
    def _convert_messages(self, messages: List[Any]):
        result = []
        logger.info(f"_convert_messages {messages}")
        for message in messages:
            parts = []
            #if message["role"] == "system":
            #    result.append(message)
            #    continue
            content = message["content"]
            if type(content) == list:
                for part in content:
                    if part["type"] == "image_url":
                        # rewrite image
                        # part["type"] = "image"
                        origin = part["image_url"]["url"]
                        del part["image_url"]
                        partial = str(origin[23:])
                        part["image"] = {
                            "format": "jpeg",
                            "source": {
                                "bytes": b64decode(partial.encode('utf-8'))
                            }
                        }
                    del part["type"]
                    parts.append(part)
            elif type(content) == str:
                parts.append({"text": content})
                    
            del message["content"]
            message["content"] = parts
            result.append(message)
        logger.info(f"after _convert_messages {result}")
        return result

@register_addon_as_extension("bedrock_llm_python")
class BedrockLLMExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        ten.on_create_instance_done(BedrockLLMExtension(addon_name), context)
