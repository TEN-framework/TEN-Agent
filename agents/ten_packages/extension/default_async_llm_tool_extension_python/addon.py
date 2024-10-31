#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import DefaultAsyncLLMToolExtension


@register_addon_as_extension("default_async_llm_tool_extension_python")
class DefaultAsyncLLMToolExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        ten_env.log_info("on_create_instance")
        ten_env.on_create_instance_done(
            DefaultAsyncLLMToolExtension(name), context)
