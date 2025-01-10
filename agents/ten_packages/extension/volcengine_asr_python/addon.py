from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)

@register_addon_as_extension("volcengine_asr_python")
class VolcengineASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .extension import VolcengineASRExtension
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(VolcengineASRExtension(addon_name), context)
