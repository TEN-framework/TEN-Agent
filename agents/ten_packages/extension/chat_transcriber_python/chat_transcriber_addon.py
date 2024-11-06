from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("chat_transcriber_python")
class ChatTranscriberExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .log import logger
        logger.info("on_create_instance")

        from .chat_transcriber_extension import ChatTranscriberExtension

        ten.on_create_instance_done(ChatTranscriberExtension(addon_name), context)

