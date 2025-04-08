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


@register_addon_as_extension("speechmatics_asr_python")
class SpeechmaticsASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        ten.log_info("on_create_instance")

        from .extension import SpeechmaticsASRExtension

        ten.on_create_instance_done(SpeechmaticsASRExtension(addon_name), context)

        ten.log_info("on_create_instance done")
