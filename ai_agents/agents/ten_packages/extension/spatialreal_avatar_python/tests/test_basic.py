#
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file for more information.
#
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


def test_basic():
    tester = ExtensionTesterBasic()
    tester.set_test_mode_single("spatialreal_avatar_python")
    err = tester.run()
    if err is not None:
        assert False, err.error_message()
