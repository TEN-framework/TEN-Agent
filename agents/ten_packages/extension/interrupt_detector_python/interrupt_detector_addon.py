#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)


@register_addon_as_extension("interrupt_detector_python")
class InterruptDetectorExtensionAddon(Addon):
    def on_create_instance(self, ten: TenEnv, addon_name: str, context) -> None:
        from .log import logger
        logger.info("on_create_instance")

        from .interrupt_detector_extension import InterruptDetectorExtension

        ten.on_create_instance_done(InterruptDetectorExtension(addon_name), context)
