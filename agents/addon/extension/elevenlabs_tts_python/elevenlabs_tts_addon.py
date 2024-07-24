#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from rte_runtime_python import (
    Addon,
    register_addon_as_extension,
    Rte,
)
from .log import logger


@register_addon_as_extension("elevenlabs_tts_python")
class ElevenlabsTTSExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logger.info("on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        from .elevenlabs_tts_extension import ElevenlabsTTSExtension

        rte.on_create_instance_done(ElevenlabsTTSExtension(addon_name), context)

    def on_deinit(self, rte: Rte) -> None:
        logger.info("on_deinit")
        rte.on_deinit_done()
        return
