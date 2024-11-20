#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-08.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("ssml_tool_python")
class SSMLToolExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import SSMLToolExtension
        from .log import logger
        logger.info("SSMLToolExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(SSMLToolExtension(name), context)
