from rte import (
    Addon,
    register_addon_as_extension,
    RteEnv,
)
from .log import logger
from .file_chunker_extension import FileChunkerExtension


@register_addon_as_extension("file_chunker")
class FileChunkerExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context) -> None:
        logger.info("on_create_instance")
        rte.on_create_instance_done(FileChunkerExtension(addon_name), context)
