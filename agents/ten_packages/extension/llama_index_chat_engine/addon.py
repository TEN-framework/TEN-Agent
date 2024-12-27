from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("llama_index_chat_engine")
class LlamaIndexChatEngineExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context):
        from .extension import LlamaIndexExtension

        ten.log_info("on_create_instance")
        ten.on_create_instance_done(LlamaIndexExtension(addon_name), context)
