#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from rte.image_frame import ImageFrame
from .openai_chatgpt import OpenAIChatGPT, OpenAIChatGPTConfig
from datetime import datetime
from threading import Thread
from rte import (
    Addon,
    Extension,
    register_addon_as_extension,
    RteEnv,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
    MetadataInfo,
)
from .log import logger
from base64 import b64encode
import numpy as np
from io import BytesIO
from PIL import Image


CMD_IN_FLUSH = "flush"
CMD_OUT_FLUSH = "flush"
DATA_IN_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_IN_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT = "end_of_segment"

PROPERTY_BASE_URL = "base_url"  # Optional
PROPERTY_API_KEY = "api_key"  # Required
PROPERTY_MODEL = "model"  # Optional
PROPERTY_PROMPT = "prompt"  # Optional
PROPERTY_FREQUENCY_PENALTY = "frequency_penalty"  # Optional
PROPERTY_PRESENCE_PENALTY = "presence_penalty"  # Optional
PROPERTY_TEMPERATURE = "temperature"  # Optional
PROPERTY_TOP_P = "top_p"  # Optional
PROPERTY_MAX_TOKENS = "max_tokens"  # Optional
PROPERTY_GREETING = "greeting"  # Optional
PROPERTY_ENABLE_VISION = "enable_vision"  # Optional
PROPERTY_PROXY_URL = "proxy_url"  # Optional
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


def yuv420_to_rgb(yuv_data, width, height):
    # Calculate the size of each plane
    frame_size = width * height
    chroma_size = frame_size // 4

    y_plane = yuv_data[0:frame_size].reshape((height, width))
    u_plane = yuv_data[frame_size:frame_size + chroma_size].reshape((height // 2, width // 2))
    v_plane = yuv_data[frame_size + chroma_size:].reshape((height // 2, width // 2))

    u_plane = u_plane.repeat(2, axis=0).repeat(2, axis=1)
    v_plane = v_plane.repeat(2, axis=0).repeat(2, axis=1)

    # Ensure calculations are done in a wider data type to prevent overflow
    y_plane = y_plane.astype(np.int16)
    u_plane = u_plane.astype(np.int16)
    v_plane = v_plane.astype(np.int16)

    # Convert YUV to RGB using the standard conversion formula
    r_plane = y_plane + 1.402 * (v_plane - 128)
    g_plane = y_plane - 0.344136 * (u_plane - 128) - 0.714136 * (v_plane - 128)
    b_plane = y_plane + 1.772 * (u_plane - 128)

    # Clip values to the 0-255 range and convert to uint8
    r_plane = np.clip(r_plane, 0, 255).astype(np.uint8)
    g_plane = np.clip(g_plane, 0, 255).astype(np.uint8)
    b_plane = np.clip(b_plane, 0, 255).astype(np.uint8)

    # Stack the RGB planes into an image
    rgb_image = np.stack([r_plane, g_plane, b_plane], axis=-1)

    return rgb_image

def yuv2base64png(yuv_data, width, height):
    # Convert YUV to RGB
    rgb_image = yuv420_to_rgb(np.frombuffer(yuv_data, dtype=np.uint8), width, height)

    # Convert the RGB image to a PIL Image
    pil_image = Image.fromarray(rgb_image)

    # Save the image to a BytesIO object in PNG format
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")

    # Get the byte data of the PNG image
    png_image_data = buffered.getvalue()

    # Convert the PNG byte data to a Base64 encoded string
    base64_encoded_image = b64encode(png_image_data).decode('utf-8')

    # Create the data URL
    mime_type = 'image/jpeg'
    base64_url = f"data:{mime_type};base64,{base64_encoded_image}"
    return base64_url

class OpenAIChatGPTExtension(Extension):
    memory = []
    max_memory_length = 10
    outdate_ts = 0
    openai_chatgpt = None
    enable_vision = False
    image_data = None
    image_width = 0
    image_height = 0

    def on_start(self, rte: RteEnv) -> None:
        logger.info("OpenAIChatGPTExtension on_start")
        # Prepare configuration
        openai_chatgpt_config = OpenAIChatGPTConfig.default_config()

        try:
            base_url = rte.get_property_string(PROPERTY_BASE_URL)
            if base_url:
                openai_chatgpt_config.base_url = base_url
        except Exception as err:
            logger.info(f"GetProperty required {PROPERTY_BASE_URL} failed, err: {err}")

        try:
            api_key = rte.get_property_string(PROPERTY_API_KEY)
            openai_chatgpt_config.api_key = api_key
        except Exception as err:
            logger.info(f"GetProperty required {PROPERTY_API_KEY} failed, err: {err}")
            return

        try:
            model = rte.get_property_string(PROPERTY_MODEL)
            if model:
                openai_chatgpt_config.model = model
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_MODEL} error: {err}")

        try:
            prompt = rte.get_property_string(PROPERTY_PROMPT)
            if prompt:
                openai_chatgpt_config.prompt = prompt
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_PROMPT} error: {err}")

        try:
            frequency_penalty = rte.get_property_float(PROPERTY_FREQUENCY_PENALTY)
            openai_chatgpt_config.frequency_penalty = float(frequency_penalty)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_FREQUENCY_PENALTY} failed, err: {err}"
            )

        try:
            presence_penalty = rte.get_property_float(PROPERTY_PRESENCE_PENALTY)
            openai_chatgpt_config.presence_penalty = float(presence_penalty)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_PRESENCE_PENALTY} failed, err: {err}"
            )

        try:
            temperature = rte.get_property_float(PROPERTY_TEMPERATURE)
            openai_chatgpt_config.temperature = float(temperature)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_TEMPERATURE} failed, err: {err}"
            )

        try:
            top_p = rte.get_property_float(PROPERTY_TOP_P)
            openai_chatgpt_config.top_p = float(top_p)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_TOP_P} failed, err: {err}")

        try:
            max_tokens = rte.get_property_int(PROPERTY_MAX_TOKENS)
            if max_tokens > 0:
                openai_chatgpt_config.max_tokens = int(max_tokens)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_MAX_TOKENS} failed, err: {err}"
            )

        try:
            proxy_url = rte.get_property_string(PROPERTY_PROXY_URL)
            openai_chatgpt_config.proxy_url = proxy_url
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_PROXY_URL} failed, err: {err}")

        try:
            greeting = rte.get_property_string(PROPERTY_GREETING)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_GREETING} failed, err: {err}")

        try:
            self.enable_vision = rte.get_property_bool(PROPERTY_ENABLE_VISION)
        except Exception as err:
            logger.info(f"GetProperty optional {PROPERTY_ENABLE_VISION} failed, err: {err}")

        try:
            prop_max_memory_length = rte.get_property_int(PROPERTY_MAX_MEMORY_LENGTH)
            if prop_max_memory_length > 0:
                self.max_memory_length = int(prop_max_memory_length)
        except Exception as err:
            logger.info(
                f"GetProperty optional {PROPERTY_MAX_MEMORY_LENGTH} failed, err: {err}"
            )

        # Create openaiChatGPT instance
        try:
            self.openai_chatgpt = OpenAIChatGPT(openai_chatgpt_config)
            logger.info(
                f"newOpenaiChatGPT succeed with max_tokens: {openai_chatgpt_config.max_tokens}, model: {openai_chatgpt_config.model}"
            )
        except Exception as err:
            logger.info(f"newOpenaiChatGPT failed, err: {err}")

        # Send greeting if available
        if greeting:
            try:
                output_data = Data.create("text_data")
                output_data.set_property_string(
                    DATA_OUT_TEXT_DATA_PROPERTY_TEXT, greeting
                )
                output_data.set_property_bool(
                    DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True
                )
                rte.send_data(output_data)
                logger.info(f"greeting [{greeting}] sent")
            except Exception as err:
                logger.info(f"greeting [{greeting}] send failed, err: {err}")
        rte.on_start_done()

    def on_stop(self, rte: RteEnv) -> None:
        logger.info("OpenAIChatGPTExtension on_stop")
        rte.on_stop_done()

    def on_cmd(self, rte: RteEnv, cmd: Cmd) -> None:
        logger.info("OpenAIChatGPTExtension on_cmd")
        cmd_json = cmd.to_json()
        logger.info("OpenAIChatGPTExtension on_cmd json: " + cmd_json)

        cmd_name = cmd.get_name()

        if cmd_name == CMD_IN_FLUSH:
            self.outdate_ts = get_current_time()
            cmd_out = Cmd.create(CMD_OUT_FLUSH)
            rte.send_cmd(cmd_out, None)
            logger.info(f"OpenAIChatGPTExtension on_cmd sent flush")
        else:
            logger.info(f"OpenAIChatGPTExtension on_cmd unknown cmd: {cmd_name}")
            cmd_result = CmdResult.create(StatusCode.ERROR)
            cmd_result.set_property_string("detail", "unknown cmd")
            rte.return_result(cmd_result, cmd)
            return

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)

    def on_image_frame(self, rte_env: RteEnv, image_frame: ImageFrame) -> None:
        # logger.info(f"OpenAIChatGPTExtension on_image_frame {image_frame.get_width()} {image_frame.get_height()}")
        self.image_data = image_frame.get_buf()
        self.image_width = image_frame.get_width()
        self.image_height = image_frame.get_height()
        return

    def on_data(self, rte: RteEnv, data: Data) -> None:
        """
        on_data receives data from rte graph.
        current supported data:
          - name: text_data
            example:
            {name: text_data, properties: {text: "hello"}
        """
        logger.info(f"OpenAIChatGPTExtension on_data")

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

        # Prepare memory
        if len(self.memory) > self.max_memory_length:
            self.memory.pop(0)
        if self.image_data is not None and self.enable_vision is True:
            url = yuv2base64png(self.image_data, self.image_width, self.image_height)
            # logger.info(f"image url: {url}")
            self.memory.append({"role": "user", "content": [
                {"type": "text", "text": input_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": url,
                    }
                }
            ]})
            # clear image after use
            self.image_data = None
        else:
            self.memory.append({"role": "user", "content": input_text})

        def chat_completions_stream_worker(start_time, input_text, memory):
            try:
                logger.info(
                    f"GetChatCompletionsStream for input text: [{input_text}] memory: {memory}"
                )

                # Get result from AI
                resp = self.openai_chatgpt.get_chat_completions_stream(memory)
                if resp is None:
                    logger.info(
                        f"GetChatCompletionsStream for input text: [{input_text}] failed"
                    )
                    return

                sentence = ""
                full_content = ""
                first_sentence_sent = False

                for chat_completions in resp:
                    if start_time < self.outdate_ts:
                        logger.info(
                            f"GetChatCompletionsStream recv interrupt and flushing for input text: [{input_text}], startTs: {start_time}, outdateTs: {self.outdate_ts}"
                        )
                        break

                    if (
                        len(chat_completions.choices) > 0
                        and chat_completions.choices[0].delta.content is not None
                    ):
                        content = chat_completions.choices[0].delta.content
                    else:
                        content = ""

                    full_content += content

                    while True:
                        sentence, content, sentence_is_final = parse_sentence(
                            sentence, content
                        )
                        if len(sentence) == 0 or not sentence_is_final:
                            logger.info(f"sentence {sentence} is empty or not final")
                            break
                        logger.info(
                            f"GetChatCompletionsStream recv for input text: [{input_text}] got sentence: [{sentence}]"
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
                            rte.send_data(output_data)
                            logger.info(
                                f"GetChatCompletionsStream recv for input text: [{input_text}] sent sentence [{sentence}]"
                            )
                        except Exception as err:
                            logger.info(
                                f"GetChatCompletionsStream recv for input text: [{input_text}] send sentence [{sentence}] failed, err: {err}"
                            )
                            break

                        sentence = ""
                        if not first_sentence_sent:
                            first_sentence_sent = True
                            logger.info(
                                f"GetChatCompletionsStream recv for input text: [{input_text}] first sentence sent, first_sentence_latency {get_current_time() - start_time}ms"
                            )

                # remember response as assistant content in memory
                memory.append({"role": "assistant", "content": full_content})

                # send end of segment
                try:
                    output_data = Data.create("text_data")
                    output_data.set_property_string(
                        DATA_OUT_TEXT_DATA_PROPERTY_TEXT, sentence
                    )
                    output_data.set_property_bool(
                        DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True
                    )
                    rte.send_data(output_data)
                    logger.info(
                        f"GetChatCompletionsStream for input text: [{input_text}] end of segment with sentence [{sentence}] sent"
                    )
                except Exception as err:
                    logger.info(
                        f"GetChatCompletionsStream for input text: [{input_text}] end of segment with sentence [{sentence}] send failed, err: {err}"
                    )

            except Exception as e:
                logger.info(
                    f"GetChatCompletionsStream for input text: [{input_text}] failed, err: {e}"
                )

        # Start thread to request and read responses from OpenAI
        start_time = get_current_time()
        thread = Thread(
            target=chat_completions_stream_worker,
            args=(start_time, input_text, self.memory),
        )
        thread.start()
        logger.info(f"OpenAIChatGPTExtension on_data end")

@register_addon_as_extension("openai_chatgpt_python")
class OpenAIChatGPTExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        rte.on_create_instance_done(OpenAIChatGPTExtension(addon_name), context)
