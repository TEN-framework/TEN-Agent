from ten_runtime import Addon, TenEnv, register_addon_as_extension


@register_addon_as_extension("bytedance_mllm_python")
class BytedanceMLLMExtensionAddon(Addon):
    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        from .extension import BytedanceMLLMExtension

        ten_env.log_info("BytedanceMLLMExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(BytedanceMLLMExtension(name), context)
