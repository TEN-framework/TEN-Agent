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


@register_addon_as_extension("neuphonic_tts")
class NeuphonicTTSExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import NeuphonicTTSExtension

        ten_env.log_info("NeuphonicTTSExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(NeuphonicTTSExtension(name), context)
