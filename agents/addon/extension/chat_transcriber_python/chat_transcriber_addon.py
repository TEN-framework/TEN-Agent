from rte_runtime_python import (
    Addon,
    register_addon_as_extension,
    Rte,
)
from .log import logger


@register_addon_as_extension("chat_transcriber_python")
class ChatTranscriberExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logger.info("on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str, context) -> None:
        logger.info("on_create_instance")

        from .chat_transcriber_extension import ChatTranscriberExtension

        rte.on_create_instance_done(ChatTranscriberExtension(addon_name), context)

    def on_deinit(self, rte: Rte) -> None:
        logger.info("on_deinit")
        rte.on_deinit_done()
        return
