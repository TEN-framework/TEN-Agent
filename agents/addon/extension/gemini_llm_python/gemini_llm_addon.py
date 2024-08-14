#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from rte import (
    Addon,
    register_addon_as_extension,
    RteEnv,
)
from .extension import EXTENSION_NAME
from .log import logger
from .gemini_llm_extension import GeminiLLMExtension


@register_addon_as_extension(EXTENSION_NAME)
class GeminiLLMExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")

        rte.on_create_instance_done(GeminiLLMExtension(addon_name), context)
