from rte import (
    Addon,
    register_addon_as_extension,
    RteEnv,
)
from .log import logger


@register_addon_as_extension("cosy_tts")
class CosyTTSExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")

        from .cosy_tts_extension import CosyTTSExtension

        rte.on_create_instance_done(CosyTTSExtension(addon_name), context)
