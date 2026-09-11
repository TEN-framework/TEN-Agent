from ten_runtime import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("cekura_metrics_python")
class CekuraMetricsExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import CekuraMetricsExtension

        ten_env.log_info("Cekura Metrics: on_create_instance")
        ten_env.on_create_instance_done(CekuraMetricsExtension(name), context)
