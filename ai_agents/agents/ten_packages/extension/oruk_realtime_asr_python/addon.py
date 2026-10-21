from ten_runtime import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)

from .extension import OrukRealtimeASRExtension


@register_addon_as_extension("oruk_realtime_asr_python")
class OrukRealtimeASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(
            OrukRealtimeASRExtension(addon_name), context
        )
