#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten_runtime import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("speko_asr_python")
class SpekoASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .extension import SpekoASRExtension

        ten.log_info("on_create_instance")
        ten.on_create_instance_done(SpekoASRExtension(addon_name), context)
