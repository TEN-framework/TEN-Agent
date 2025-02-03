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


@register_addon_as_extension("aisuite_llm_python")
class AISuiteLLMExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context):
        from .aisuite_llm_extension import AISuiteLLMExtension

        ten.log_info("on_create_instance")
        ten.on_create_instance_done(AISuiteLLMExtension(addon_name), context)
