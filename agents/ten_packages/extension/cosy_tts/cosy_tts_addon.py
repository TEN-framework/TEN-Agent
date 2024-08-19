from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .log import logger


@register_addon_as_extension("cosy_tts")
class CosyTTSExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")

        from .cosy_tts_extension import CosyTTSExtension

        ten.on_create_instance_done(CosyTTSExtension(addon_name), context)
