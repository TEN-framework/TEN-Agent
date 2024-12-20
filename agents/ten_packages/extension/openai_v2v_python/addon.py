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


@register_addon_as_extension("openai_v2v_python")
class OpenAIRealtimeExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import OpenAIRealtimeExtension

        ten_env.log_info("OpenAIRealtimeExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(OpenAIRealtimeExtension(name), context)
