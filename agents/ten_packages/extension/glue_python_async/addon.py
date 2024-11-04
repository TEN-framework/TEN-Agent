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
from .extension import AsyncGlueExtension
from .log import logger


@register_addon_as_extension("glue_python_async")
class AsyncGlueExtensionAddon(Addon):

    def on_create_instance(self, ten_env: TenEnv, name: str, context) -> None:
        logger.info("AsyncGlueExtensionAddon on_create_instance")
        ten_env.on_create_instance_done(AsyncGlueExtension(name), context)
