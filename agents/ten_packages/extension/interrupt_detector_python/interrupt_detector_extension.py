#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from ten import (
    Extension,
    TenEnv,
    Cmd,
    Data,
    StatusCode,
    CmdResult,
)
from .log import logger


CMD_NAME_FLUSH = "flush"

TEXT_DATA_TEXT_FIELD = "text"
TEXT_DATA_FINAL_FIELD = "is_final"


class InterruptDetectorExtension(Extension):
    def on_start(self, ten: TenEnv) -> None:
        logger.info("on_start")
        ten.on_start_done()

    def on_stop(self, ten: TenEnv) -> None:
        logger.info("on_stop")
        ten.on_stop_done()

    def send_flush_cmd(self, ten: TenEnv) -> None:
        flush_cmd = Cmd.create(CMD_NAME_FLUSH)
        ten.send_cmd(
            flush_cmd,
            lambda ten, result: logger.info("send_cmd done"),
        )

        logger.info(f"sent cmd: {CMD_NAME_FLUSH}")

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        cmd_name = cmd.get_name()
        logger.info("on_cmd name {}".format(cmd_name))

        # flush whatever cmd incoming at the moment
        self.send_flush_cmd(ten)

        # then forward the cmd to downstream
        cmd_json = cmd.to_json()
        new_cmd = Cmd.create_from_json(cmd_json)
        ten.send_cmd(
            new_cmd,
            lambda ten, result: logger.info("send_cmd done"),
        )

        cmd_result = CmdResult.create(StatusCode.OK)
        ten.return_result(cmd_result, cmd)

    def on_data(self, ten: TenEnv, data: Data) -> None:
        """
        on_data receives data from ten graph.
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
            self.send_flush_cmd(ten)

        d = Data.create("text_data")
        d.set_property_bool(TEXT_DATA_FINAL_FIELD, final)
        d.set_property_string(TEXT_DATA_TEXT_FIELD, text)
        ten.send_data(d)
