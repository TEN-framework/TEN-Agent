from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("aliyun_analyticdb_vector_storage")
class AliPGDBExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .vector_storage_extension import AliPGDBExtension
        ten.log_info("on_create_instance")
        ten.on_create_instance_done(AliPGDBExtension(addon_name), context)
