#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from .openai_chatgpt import OpenAIChatGPT, OpenAIChatGPTConfig
from rte_runtime_python import (
    Addon,
    Extension,
    register_addon_as_extension,
    Rte,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
    MetadataInfo,
    RTE_PIXEL_FMT,
)
from rte_runtime_python.image_frame import ImageFrame
from PIL import Image, ImageFilter


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
PROPERTY_PROXY_URL = "proxy_url"  # Optional
PROPERTY_MAX_MEMORY_LENGTH = "max_memory_length"  # Optional

memory = []
max_memory_length = 10

class OpenAIChatGPTExtension(Extension):
    def on_init(self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo) -> None:
        print("OpenAIChatGPTExtension on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        print("OpenAIChatGPTExtension on_start")
        # Prepare configuration
        openai_chatgpt_config = OpenAIChatGPTConfig.default_config()

        try:
            base_url = rte.get_property_string(PROPERTY_BASE_URL)
            if base_url:
                openai_chatgpt_config.BaseUrl = base_url
        except Exception as err:
            print(f"GetProperty required {PROPERTY_BASE_URL} failed, err: {err}")

        try:
            api_key = rte.get_property_string(PROPERTY_API_KEY)
            openai_chatgpt_config.ApiKey = api_key
        except Exception as err:
            print(f"GetProperty required {PROPERTY_API_KEY} failed, err: {err}")

        try:
            model = rte.get_property_string(PROPERTY_MODEL)
            if model:
                openai_chatgpt_config.Model = model
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_MODEL} error: {err}")

        try:
            prompt = rte.get_property_string(PROPERTY_PROMPT)
            if prompt:
                openai_chatgpt_config.Prompt = prompt
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_PROMPT} error: {err}")

        try:
            frequency_penalty = rte.get_property_float(PROPERTY_FREQUENCY_PENALTY)
            openai_chatgpt_config.FrequencyPenalty = float(frequency_penalty)
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_FREQUENCY_PENALTY} failed, err: {err}")

        try:
            presence_penalty = rte.get_property_float(PROPERTY_PRESENCE_PENALTY)
            openai_chatgpt_config.PresencePenalty = float(presence_penalty)
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_PRESENCE_PENALTY} failed, err: {err}")

        try:
            temperature = rte.get_property_float(PROPERTY_TEMPERATURE)
            openai_chatgpt_config.Temperature = float(temperature)
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_TEMPERATURE} failed, err: {err}")

        try:
            top_p = rte.get_property_float(PROPERTY_TOP_P)
            openai_chatgpt_config.TopP = float(top_p)
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_TOP_P} failed, err: {err}")

        try:
            max_tokens = rte.get_property_int(PROPERTY_MAX_TOKENS)
            if max_tokens > 0:
                openai_chatgpt_config.MaxTokens = int(max_tokens)
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_MAX_TOKENS} failed, err: {err}")

        try:
            proxy_url = rte.get_property_string(PROPERTY_PROXY_URL)
            openai_chatgpt_config.ProxyUrl = proxy_url
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_PROXY_URL} failed, err: {err}")

        try:
            greeting = rte.get_property_string(PROPERTY_GREETING)
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_GREETING} failed, err: {err}")

        try:
            prop_max_memory_length = rte.get_property_int(PROPERTY_MAX_MEMORY_LENGTH)
            if prop_max_memory_length > 0:
                max_memory_length = int(prop_max_memory_length)
        except Exception as err:
            print(f"GetProperty optional {PROPERTY_MAX_MEMORY_LENGTH} failed, err: {err}")

        # Create openaiChatGPT instance
        try:
            openai_chatgpt = OpenAIChatGPT(openai_chatgpt_config)
            print(f"newOpenaiChatGPT succeed with max_tokens: {openai_chatgpt_config.MaxTokens}, model: {openai_chatgpt_config.Model}")
        except Exception as err:
            print(f"newOpenaiChatGPT failed, err: {err}")

        # Send greeting if available
        if greeting:
            try:
                output_data = Data.create("text_data")
                output_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, greeting)
                output_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_TEXT_END_OF_SEGMENT, True)
                rte.send_data(output_data)
                print(f"greeting [{greeting}] sent")
            except Exception as err:
                print(f"greeting [{greeting}] send failed, err: {err}")
        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        print("OpenAIChatGPTExtension on_stop")
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        print("OpenAIChatGPTExtension on_deinit")
        rte.on_deinit_done()

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        print("OpenAIChatGPTExtension on_cmd")
        cmd_json = cmd.to_json()
        print("OpenAIChatGPTExtension on_cmd json: " + cmd_json)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)

    def on_image_frame(self, rte: Rte, image_frame: ImageFrame) -> None:
        print("OpenAIChatGPTExtension on_cmd")

    def on_data(self, rte: Rte, data: Data) -> None:
        """
        on_data receives data from rte graph.
        current supported data:
          - name: text_data
            example:
            {name: text_data, properties: {text: "hello"}
        """
        print(f"OpenAIChatGPTExtension on_data")

        try:
            rte_data = Data.create("text_data")
            rte_data.set_property_string("text", "hello, world, who are you!")
        except Exception as e:
            print(f"on_data new_data error, ", e)
            return

        rte.send_data(rte_data)


@register_addon_as_extension("openai_chatgpt_python")
class OpenAIChatGPTExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        print("OpenAIChatGPTExtensionAddon on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str, context) -> None:
        print("on_create_instance")
        rte.on_create_instance_done(OpenAIChatGPTExtension(addon_name), context)

    def on_deinit(self, rte: Rte) -> None:
        print("OpenAIChatGPTExtensionAddon on_deinit")
        rte.on_deinit_done()
        return
