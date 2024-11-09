from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import EXTENSION_NAME


@register_addon_as_extension(EXTENSION_NAME)
class TranscribeAsrExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .log import logger
        from .transcribe_asr_extension import TranscribeAsrExtension
        logger.info("on_create_instance")
        ten.on_create_instance_done(TranscribeAsrExtension(addon_name), context)
