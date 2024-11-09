#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import EXTENSION_NAME


@register_addon_as_extension(EXTENSION_NAME)
class CartesiaTTSExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .log import logger
        logger.info("on_create_instance")
        from .cartesia_tts_extension import CartesiaTTSExtension

        ten.on_create_instance_done(CartesiaTTSExtension(addon_name), context)
