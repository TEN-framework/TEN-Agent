#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
import json

from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Cmd,
    StatusCode,
    LogLevel,
    TenError,
    TenErrorCode,
)


class ExtensionTesterBasic(AsyncExtensionTester):
    async def on_start(self, ten_env: AsyncTenEnvTester) -> None:
        new_cmd = Cmd.create("hello_world")

        ten_env.log(LogLevel.DEBUG, "send hello_world")
        result, err = await ten_env.send_cmd(new_cmd)
        if (
            err is not None
            or result is None
            or result.get_status_code() != StatusCode.OK
        ):
            ten_env.stop_test(
                TenError.create(
                    TenErrorCode.ErrorCodeGeneric,
                    "Failed to send hello_world",
                )
            )
        else:
            ten_env.stop_test()

        ten_env.log(LogLevel.DEBUG, "tester on_start_done")


def test_ten_runtime_loads_extension_and_handles_command():
    tester = ExtensionTesterBasic()
    tester.set_test_mode_single(
        "iflytek_asr_python",
        json.dumps(
            {
                "params": {
                    "url": "ws://127.0.0.1:1/tuling/ast/v3",
                    "biz_id": "runtime-smoke-test",
                    "connect_timeout": 0.1,
                    "reconnect_delay": 0,
                    "reconnect_max_delay": 0,
                    "reconnect_max_attempts": 1,
                }
            }
        ),
    )
    err = tester.run()
    if err is not None:
        assert False, err.error_message()
