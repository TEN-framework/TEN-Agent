#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .log import logger


@register_addon_as_extension("qwen_llm_python")
class QWenLLMExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context):
        logger.info("on_create_instance")

        from .qwen_llm_extension import QWenLLMExtension

        ten.on_create_instance_done(QWenLLMExtension(addon_name), context)

