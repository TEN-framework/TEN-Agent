from rte import (
    Addon,
    register_addon_as_extension,
    RteEnv,
)
from .extension import EXTENSION_NAME
from .log import logger
from .polly_tts_extension import PollyTTSExtension


@register_addon_as_extension(EXTENSION_NAME)
class PollyTTSExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        rte.on_create_instance_done(PollyTTSExtension(addon_name), context)
