from rte_runtime_python import (
    Addon,
    register_addon_as_extension,
    Rte,
)
from .log import logger


@register_addon_as_extension("cosy_tts")
class CosyTTSExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logger.info("CosyTTSExtensionAddon on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str, context) -> None:
        logger.info("on_create_instance")

        from .cosy_tts_extension import CosyTTSExtension

        rte.on_create_instance_done(CosyTTSExtension(addon_name), context)

    def on_deinit(self, rte: Rte) -> None:
        logger.info("CosyTTSExtensionAddon on_deinit")
        rte.on_deinit_done()
        return
