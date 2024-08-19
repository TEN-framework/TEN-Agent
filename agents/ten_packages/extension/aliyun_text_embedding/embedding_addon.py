from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .log import logger
from .embedding_extension import EmbeddingExtension


@register_addon_as_extension("aliyun_text_embedding")
class EmbeddingExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        ten.on_create_instance_done(EmbeddingExtension(addon_name), context)
