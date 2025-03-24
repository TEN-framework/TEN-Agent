from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)

@register_addon_as_extension("aliyun_asr")
class AliyunASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .extension import AliyunASRExtension
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(AliyunASRExtension(addon_name), context)
