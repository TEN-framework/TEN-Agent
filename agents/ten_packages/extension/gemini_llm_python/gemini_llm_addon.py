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

@register_addon_as_extension("gemini_llm_python")
class GeminiLLMExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .gemini_llm_extension import GeminiLLMExtension
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(GeminiLLMExtension(addon_name), context)
