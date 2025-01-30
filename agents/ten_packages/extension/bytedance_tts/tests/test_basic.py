#
# Copyright © 2024 Agora
# This file is part of TEN Framework, an open source project.
# Licensed under the Apache License, Version 2.0, with certain conditions.
# Refer to the "LICENSE" file in the root directory for more information.
#
from pathlib import Path
from ten import ExtensionTester, TenEnvTester, AudioFrame, Data
import os


class ExtensionTesterBasic(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.dump_pcm = True

    def on_audio_frame(
        self, ten_env_tester: TenEnvTester, audio_frame: AudioFrame
    ) -> None:
        if self.dump_pcm:
            buf = audio_frame.lock_buf()
            with open("test.pcm", "ab") as f:
                f.write(buf)

            audio_frame.unlock_buf()

    def on_start(self, ten_env: TenEnvTester) -> None:
        # Text to be synthesized.
        data = Data.create("text_data")
        data.set_property_string(
            "text",
            """
            传入1时表示启用。新版时间戳参数，可用来替换with_frontend和frontend_type，
            可返回原文本的时间戳，而非TN后文本，即保留原文中的阿拉伯数字或者特殊符号等。
            注意：原文本中的多个标点连用或者空格依然会被处理，但不影响时间戳连贯性。
            """,
        )
        data.set_property_bool("end_of_segment", True)
        ten_env.send_data(data)

        print("tester on_start_done")
        ten_env.on_start_done()


def test_basic():
    env = os.environ.copy()
    env["BYTEDANCE_TTS_APPID"] = "your appid"
    env["BYTEDANCE_TTS_TOKEN"] = "your token"

    tester = ExtensionTesterBasic()
    tester.add_addon_base_dir(str(Path(__file__).resolve().parent.parent))
    tester.set_test_mode_single("default_async_extension_python")
    tester.run()
