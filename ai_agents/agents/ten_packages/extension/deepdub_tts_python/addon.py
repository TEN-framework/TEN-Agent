from ten_runtime import Addon, register_addon_as_extension, TenEnv


@register_addon_as_extension("deepdub_tts_python")
class DeepdubTTSExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import DeepdubTTSExtension

        ten_env.log_info("DeepdubTTSExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(DeepdubTTSExtension(name), context)
