"""
Addon registration for the Gradium real-time speech-to-speech translation
extension.
"""

from ten_runtime import Addon, TenEnv, register_addon_as_extension


@register_addon_as_extension("gradium_mllm_python")
class GradiumMLLMExtensionAddon(Addon):
    """Addon class for registering the Gradium MLLM extension."""

    def on_create_instance(
        self, ten_env: TenEnv, addon_name: str, context
    ) -> None:
        from .extension import GradiumMLLMExtension

        ten_env.log_info(
            f"Creating Gradium MLLM extension instance: {addon_name}"
        )
        ten_env.on_create_instance_done(
            GradiumMLLMExtension(addon_name), context
        )
