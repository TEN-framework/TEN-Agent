from rte import (
    Addon,
    register_addon_as_extension,
    RteEnv,
)
from .log import logger
from .http_server_extension import HTTPServerExtension


@register_addon_as_extension("http_server_python")
class HTTPServerExtensionAddon(Addon):
    def on_create_instance(self, rte: RteEnv, addon_name: str, context):
        logger.info("on_create_instance")
        rte.on_create_instance_done(HTTPServerExtension(addon_name), context)
