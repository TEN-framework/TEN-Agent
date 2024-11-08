from ten import Addon, register_addon_as_extension, TenEnv


@register_addon_as_extension("llama_index_chat_engine")
class LlamaIndexExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .extension import LlamaIndexExtension
        from .log import logger
        logger.info("on_create_instance")
        ten.on_create_instance_done(LlamaIndexExtension(addon_name), context)
