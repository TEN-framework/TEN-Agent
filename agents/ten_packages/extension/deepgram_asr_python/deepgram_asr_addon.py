from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import EXTENSION_NAME

@register_addon_as_extension(EXTENSION_NAME)
class DeepgramASRExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .log import logger
        from .deepgram_asr_extension import DeepgramASRExtension
        logger.info("on_create_instance")
        ten.on_create_instance_done(DeepgramASRExtension(addon_name), context)
