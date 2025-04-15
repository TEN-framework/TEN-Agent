from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("sensevoice_asr_python")
class SenseVoiceASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .extension import SenseVoiceASRExtension

        ten.log_info("on_create_instance")
        ten.on_create_instance_done(SenseVoiceASRExtension(addon_name), context)
