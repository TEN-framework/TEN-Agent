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


@register_addon_as_extension("bytedance_tts")
class BytedanceTTSExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import BytedanceTTSExtension

        ten_env.log_info("BytedanceTTSExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(BytedanceTTSExtension(name), context)
