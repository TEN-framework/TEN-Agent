#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from rte_runtime_python import (
    Extension,
    Rte,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
    MetadataInfo,
)
from .log import logger


CMD_NAME_FLUSH = "flush"

TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"


class InterruptDetectorExtension(Extension):
    def on_init(self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo) -> None:
        logger.info("on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        logger.info("on_start")
        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        logger.info("on_stop")
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        logger.info("on_deinit")
        rte.on_deinit_done()

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        logger.info("on_cmd")
        cmd_json = cmd.to_json()
        logger.info("on_cmd json: " % cmd_json)

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        rte.return_result(cmd_result, cmd)

    def on_data(self, rte: Rte, data: Data) -> None:
        """
        on_data receives data from rte graph.
        current supported data:
          - name: text_data
            example:
            {name: text_data, properties: {text: "hello", is_final: false}
        """
        logger.info(f"on_data")

        try:
            text = data.get_property_string(TEXT_DATA_TEXT_FIELD)
        except Exception as e:
            logger.warning(
                f"on_data get_property_string {TEXT_DATA_TEXT_FIELD} error: {e}"
            )
            return

        try:
            final = data.get_property_bool(TEXT_DATA_FINAL_FIELD)
        except Exception as e:
            logger.warning(
                f"on_data get_property_bool {TEXT_DATA_FINAL_FIELD} error: {e}"
            )
            return

        logger.debug(
            f"on_data {TEXT_DATA_TEXT_FIELD}: {text} {TEXT_DATA_FINAL_FIELD}: {final}"
        )

        if final or len(text) >= 2:
            flush_cmd = Cmd.create(CMD_NAME_FLUSH)
            rte.send_cmd(
                flush_cmd,
                lambda rte, result: print(
                    "InterruptDetectorExtensionAddon send_cmd done"
                ),
            )

            logger.info(f"sent cmd: {CMD_NAME_FLUSH}")

        d = Data.create("text_data")
        d.set_property_bool(TEXT_DATA_FINAL_FIELD, final)
        d.set_property_string(TEXT_DATA_TEXT_FIELD, text)
        rte.send_data(d)
