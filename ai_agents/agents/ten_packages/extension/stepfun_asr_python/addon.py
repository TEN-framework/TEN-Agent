from ten_runtime import Addon, TenEnv, register_addon_as_extension

from .extension import StepFunASRExtension


@register_addon_as_extension("stepfun_asr_python")
class StepFunASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, name: str, context) -> None:
        ten.on_create_instance_done(StepFunASRExtension(name), context)
