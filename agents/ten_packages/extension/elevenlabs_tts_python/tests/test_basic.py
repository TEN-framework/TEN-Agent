#
# Copyright © 2024 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
from pathlib import Path
from ten import ExtensionTester, TenEnvTester, Cmd, CmdResult, StatusCode


class ExtensionTesterBasic(ExtensionTester):
    def check_hello(self, ten_env: TenEnvTester, result: CmdResult):
        statusCode = result.get_status_code()
        print("receive hello_world, status:" + str(statusCode))

        if statusCode == StatusCode.OK:
            # TODO: move stop_test() to where the test passes
            ten_env.stop_test()

    def on_start(self, ten_env: TenEnvTester) -> None:
        new_cmd = Cmd.create("hello_world")

        print("send hello_world")
        ten_env.send_cmd(
            new_cmd,
            lambda ten_env, result,_: self.check_hello(ten_env, result),
        )

        print("tester on_start_done")
        ten_env.on_start_done()


def test_basic():
    tester = ExtensionTesterBasic()
    tester.set_test_mode_single("elevenlabs_tts_python")
    tester.run()
