from rte import (
    Addon,
    register_addon_as_extension,
    RteEnv,
)
from .log import logger
from .embedding_extension import EmbeddingExtension


@register_addon_as_extension("aliyun_text_embedding")
class EmbeddingExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        rte.on_create_instance_done(EmbeddingExtension(addon_name), context)
