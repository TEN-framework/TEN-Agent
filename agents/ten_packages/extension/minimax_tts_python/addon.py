#
#
# Agora Real Time Engagement
# Created by Tomas Liu/XinHui Li in 2024.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import MinimaxTTSExtension
from .log import logger


@register_addon_as_extension("minimax_tts_python")
class MinimaxTTSExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        logger.info("on_create_instance")
        ten_env.on_create_instance_done(MinimaxTTSExtension(name), context)
