#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from rte_runtime_python import (
    Addon,
    Extension,
    register_addon_as_extension,
    Rte,
    Cmd,
    StatusCode,
    CmdResult,
    MetadataInfo,
    RTE_PIXEL_FMT,
)
from rte_runtime_python.image_frame import ImageFrame
from PIL import Image, ImageFilter


class OpenAIChatGPTExtension(Extension):
    def on_init(self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo) -> None:
        print("OpenAIChatGPTExtension on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        print("OpenAIChatGPTExtension on_start")
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
