#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import EXTENSION_NAME
from .log import logger
from .litellm_extension import LiteLLMExtension


@register_addon_as_extension(EXTENSION_NAME)
class LiteLLMExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")

        ten.on_create_instance_done(LiteLLMExtension(addon_name), context)
