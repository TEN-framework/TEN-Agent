#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

import logging
from rte_runtime_python import (
    Addon,
    Extension,
    register_addon_as_extension,
    Rte,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
    MetadataInfo,
)

CMD_NAME_FLUSH = "flush"

TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(process)d - [%(filename)s:%(lineno)d] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
    encoding="utf-8",
)


class InterruptDetectorExtension(Extension):
    def on_init(self, rte: Rte, manifest: MetadataInfo, property: MetadataInfo) -> None:
        logging.info("on_init")
        rte.on_init_done(manifest, property)

    def on_start(self, rte: Rte) -> None:
        logging.info("on_start")
        rte.on_start_done()

    def on_stop(self, rte: Rte) -> None:
        logging.info("on_stop")
        rte.on_stop_done()

    def on_deinit(self, rte: Rte) -> None:
        logging.info("on_deinit")
        rte.on_deinit_done()

    def on_cmd(self, rte: Rte, cmd: Cmd) -> None:
        logging.info("on_cmd")
        cmd_json = cmd.to_json()
        logging.info("on_cmd json: " % cmd_json)

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
        try:
            text = data.get_property_string(TEXT_DATA_TEXT_FIELD)
        except Exception as e:
            logging.warning(
                f"on_data get_property_string {TEXT_DATA_TEXT_FIELD} error: {e}"
            )
            return

        try:
            final = data.get_property_bool(TEXT_DATA_FINAL_FIELD)
        except Exception as e:
            logging.warning(
                f"on_data get_property_bool {TEXT_DATA_FINAL_FIELD} error: {e}"
            )
            return

        logging.debug(
            f"on_data {TEXT_DATA_TEXT_FIELD}: {text} {TEXT_DATA_FINAL_FIELD}: {final}"
        )

        if final or len(text) >= 2:
            flush_cmd = rte.new_cmd(CMD_NAME_FLUSH)
            rte.send_cmd(flush_cmd, None)

            logging.info(f"sent cmd: {CMD_NAME_FLUSH}")


@register_addon_as_extension("interrupt_detector_python")
class InterruptDetectorExtensionAddon(Addon):
    def on_init(self, rte: Rte, manifest, property) -> None:
        logging.info("on_init")
        rte.on_init_done(manifest, property)
        return

    def on_create_instance(self, rte: Rte, addon_name: str) -> Extension:
        logging.info("on_create_instance")
        return InterruptDetectorExtension(addon_name)

    def on_deinit(self, rte: Rte) -> None:
        logging.info("on_deinit")
        rte.on_deinit_done()
        return
