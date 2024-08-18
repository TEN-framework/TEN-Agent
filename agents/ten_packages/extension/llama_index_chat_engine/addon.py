from rte import Addon, register_addon_as_extension, RteEnv
from .extension import LlamaIndexExtension
from .log import logger


@register_addon_as_extension("llama_index_chat_engine")
class LlamaIndexExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        rte.on_create_instance_done(LlamaIndexExtension(addon_name), context)
