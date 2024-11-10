#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
from ten import (
    Addon,
    register_addon_as_extension,
    TenEnv,
)
from .extension import VisionAnalyzeToolExtension
from .log import logger


@register_addon_as_extension("vision_analyze_tool_python")
class VisionAnalyzeToolExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        logger.info("VisionAnalyzeToolExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(VisionAnalyzeToolExtension(name), context)
