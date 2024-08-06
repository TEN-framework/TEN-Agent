#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
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


@register_addon_as_extension(EXTENSION_NAME)
class ElevenlabsTTSExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        from .elevenlabs_tts_extension import ElevenlabsTTSExtension

        rte.on_create_instance_done(ElevenlabsTTSExtension(addon_name), context)
