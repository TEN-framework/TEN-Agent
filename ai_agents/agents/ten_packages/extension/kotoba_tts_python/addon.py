#
# Kotoba TTS extension for the TEN framework.
# Licensed under the Apache License, Version 2.0.
#
from ten_runtime import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("kotoba_tts_python")
class KotobaTTSExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import KotobaTTSExtension

        ten_env.log_info("KotobaTTSExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(KotobaTTSExtension(name), context)
