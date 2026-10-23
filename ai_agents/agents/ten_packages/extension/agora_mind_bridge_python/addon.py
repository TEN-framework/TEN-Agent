from ten_runtime import Addon, register_addon_as_extension

from .extension import AgoraMindBridgeExtension


@register_addon_as_extension("agora_mind_bridge_python")
class AgoraMindBridgeExtensionAddon(Addon):
    def on_create_instance(self, ten, name, context):
        ten.on_create_instance_done(AgoraMindBridgeExtension(name), context)
