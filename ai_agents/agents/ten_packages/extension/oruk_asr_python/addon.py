from ten_runtime import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)

from .extension import OrukASRExtension


@register_addon_as_extension("oruk_asr_python")
class OrukASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(OrukASRExtension(addon_name), context)
