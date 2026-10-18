from ten_runtime import Addon, TenEnv, register_addon_as_extension


@register_addon_as_extension("typesafe_jev_python")
class TypeSafeJevAddon(Addon):
    def on_create_instance(self, ten: TenEnv, name: str, context) -> None:
        from .extension import TypeSafeJevExtension

        ten.on_create_instance_done(TypeSafeJevExtension(name), context)
