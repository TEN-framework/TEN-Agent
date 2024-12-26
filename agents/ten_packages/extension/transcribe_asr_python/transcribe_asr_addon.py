from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("transcribe_asr_python")
class TranscribeAsrExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .transcribe_asr_extension import TranscribeAsrExtension
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(TranscribeAsrExtension(addon_name), context)
