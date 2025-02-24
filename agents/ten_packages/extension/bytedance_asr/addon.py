from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)

@register_addon_as_extension("bytedance_asr")
class BytedanceASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .extension import BytedanceASRExtension
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(BytedanceASRExtension(addon_name), context)
