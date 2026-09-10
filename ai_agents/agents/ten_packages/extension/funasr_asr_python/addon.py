#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
#

from ten_runtime import Addon, register_addon_as_extension, TenEnv


@register_addon_as_extension("funasr_asr_python")
class FunASRExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import FunASRExtension

        ten_env.log_info("FunASRExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(FunASRExtension(name), context)
