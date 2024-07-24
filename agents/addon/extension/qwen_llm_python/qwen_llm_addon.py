#
#
# Agora Real Time Engagement
# Created by Wei Hu in 2024-05.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#
from rte_runtime_python import (
    Addon,
    register_addon_as_extension,
    Rte,
)
from .log import logger


@register_addon_as_extension("qwen_llm_python")
class QWenLLMExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logger.info("QWenLLMExtensionAddon on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str, context):
        logger.info("on_create_instance")

        from .qwen_llm_extension import QWenLLMExtension

        rte.on_create_instance_done(QWenLLMExtension(addon_name), context)

    def on_deinit(self, rte: Rte) -> None:
        logger.info("QWenLLMExtensionAddon on_deinit")
        rte.on_deinit_done()
        return
