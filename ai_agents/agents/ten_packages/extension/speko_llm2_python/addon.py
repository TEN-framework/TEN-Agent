#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten_runtime import Addon, TenEnv, register_addon_as_extension


@register_addon_as_extension("speko_llm2_python")
class SpekoLLM2ExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import SpekoLLM2Extension

        ten_env.log_info("SpekoLLM2ExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(SpekoLLM2Extension(name), context)
