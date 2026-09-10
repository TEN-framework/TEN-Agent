import sys
from pathlib import Path

# Project root is 6 levels up from this file's parent.
project_root = str(Path(__file__).resolve().parents[6])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import filecmp
import json
import os
import shutil
import threading
from unittest.mock import patch, AsyncMock

from ten_runtime import ExtensionTester, TenEnvTester, Data
from ten_ai_base.struct import TTSTextInput, TTSFlush


# Shared mock-wiring helper.
def _install_client_mock(mock_class):
    mock_instance = mock_class.return_value
    mock_instance.start = AsyncMock()
    mock_instance.stop = AsyncMock()
    mock_instance.cancel = AsyncMock()
    mock_instance.send_text = AsyncMock()
    mock_instance.wait_ready = AsyncMock()
    mock_instance.send_cancel = AsyncMock()

    def ctor(config, ten_env, on_audio, on_finish, on_error):
        mock_instance.on_audio = on_audio
        mock_instance.on_finish = on_finish
        mock_instance.on_error = on_error
        return mock_instance

    mock_class.side_effect = ctor
    return mock_instance


# ================ basic happy path + dump file comparison ================
class ExtensionTesterDump(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.dump_dir = "./dump/"
        self.test_dump_file_path = os.path.join(
            self.dump_dir, "test_manual_dump.pcm"
        )
        self.audio_end_received = False
        self.received_audio_chunks = []

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        ten_env_tester.log_info("Dump test started, sending TTS request.")
        tts_input = TTSTextInput(
            request_id="tts_request_1",
            text="hello world, this is a deepdub test",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        if data.get_name() == "tts_audio_end":
            self.audio_end_received = True
            ten_env.stop_test()

    def on_audio_frame(self, ten_env: TenEnvTester, audio_frame):
        buf = audio_frame.lock_buf()
        try:
            self.received_audio_chunks.append(bytes(buf))
        finally:
            audio_frame.unlock_buf(buf)

    def write_test_dump_file(self):
        with open(self.test_dump_file_path, "wb") as f:
            for chunk in self.received_audio_chunks:
                f.write(chunk)

    def find_tts_dump_file(self) -> str | None:
        if not os.path.exists(self.dump_dir):
            return None
        for filename in os.listdir(self.dump_dir):
            if filename.endswith(".pcm") and filename != os.path.basename(
                self.test_dump_file_path
            ):
                return os.path.join(self.dump_dir, filename)
        return None


@patch("deepdub_tts_python.extension.DeepdubStreamingClient")
def test_dump_functionality(MockClient):
    DUMP_PATH = "./dump/"
    if os.path.exists(DUMP_PATH):
        shutil.rmtree(DUMP_PATH)
    os.makedirs(DUMP_PATH)

    mock_instance = _install_client_mock(MockClient)

    fake_chunk_1 = b"\x11\x22\x33\x44" * 20
    fake_chunk_2 = b"\xaa\xbb\xcc\xdd" * 20

    async def stream_audio(text: str):
        await mock_instance.on_audio(fake_chunk_1)
        await asyncio.sleep(0.01)
        await mock_instance.on_audio(fake_chunk_2)
        await asyncio.sleep(0.01)
        await mock_instance.on_finish()

    async def mock_send_text(text: str):
        # text_input_end is set *after* send_text returns in request_tts;
        # schedule the simulated stream so awaiting_finish is True when on_finish fires.
        asyncio.create_task(stream_audio(text))

    mock_instance.send_text.side_effect = mock_send_text

    tester = ExtensionTesterDump()
    dump_config = {
        "params": {
            "api_key": "valid_key",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "valid_voice",
        },
        "dump": True,
        "dump_path": DUMP_PATH,
    }
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(dump_config))

    try:
        tester.run()
        assert tester.audio_end_received, "tts_audio_end was not received"

        tester.write_test_dump_file()
        assert os.path.exists(tester.test_dump_file_path)

        tts_dump_file = tester.find_tts_dump_file()
        assert (
            tts_dump_file is not None
        ), f"Could not find TTS-generated dump file in {DUMP_PATH}"

        assert filecmp.cmp(
            tts_dump_file, tester.test_dump_file_path, shallow=False
        ), "Extension dump and test-collected audio differ."
    finally:
        if os.path.exists(DUMP_PATH):
            shutil.rmtree(DUMP_PATH)


# ================ flush / cancel mid-stream ================
class ExtensionTesterFlush(ExtensionTester):
    def __init__(self):
        super().__init__()
        self.ten_env: TenEnvTester | None = None
        self.audio_start_received = False
        self.first_audio_frame_received = False
        self.flush_start_received = False
        self.audio_end_received = False
        self.flush_end_received = False
        self.audio_received_after_flush_end = False
        self.received_audio_bytes = 0

    def on_start(self, ten_env_tester: TenEnvTester) -> None:
        self.ten_env = ten_env_tester
        tts_input = TTSTextInput(
            request_id="flush_req",
            text="A long enough sentence so we can interrupt mid-stream.",
            text_input_end=True,
        )
        data = Data.create("tts_text_input")
        data.set_property_from_json(None, tts_input.model_dump_json())
        ten_env_tester.send_data(data)
        ten_env_tester.on_start_done()

    def on_audio_frame(self, ten_env: TenEnvTester, audio_frame):
        if self.flush_end_received:
            self.audio_received_after_flush_end = True
        if not self.first_audio_frame_received:
            self.first_audio_frame_received = True
            flush_data = Data.create("tts_flush")
            flush_data.set_property_from_json(
                None, TTSFlush(flush_id="flush_req").model_dump_json()
            )
            ten_env.send_data(flush_data)
        buf = audio_frame.lock_buf()
        try:
            self.received_audio_bytes += len(buf)
        finally:
            audio_frame.unlock_buf(buf)

    def on_data(self, ten_env: TenEnvTester, data) -> None:
        name = data.get_name()
        if name == "tts_audio_start":
            self.audio_start_received = True
            return
        if name == "tts_flush_start":
            self.flush_start_received = True
            return
        json_str, _ = data.get_property_to_json(None)
        if not json_str:
            return
        if name == "tts_audio_end":
            self.audio_end_received = True
        elif name == "tts_flush_end":
            self.flush_end_received = True
            timer = threading.Timer(0.3, ten_env.stop_test)
            timer.start()


@patch("deepdub_tts_python.extension.DeepdubStreamingClient")
def test_flush_logic(MockClient):
    mock_instance = _install_client_mock(MockClient)

    async def stream_long(text: str):
        # Stream many chunks until cancel() is called by the extension.
        for _ in range(40):
            if mock_instance.cancel.called:
                # Vendor finishes the burst with a finish boundary.
                await mock_instance.on_finish()
                return
            await mock_instance.on_audio(b"\x11\x22\x33" * 100)
            await asyncio.sleep(0.05)
        await mock_instance.on_finish()

    async def mock_send_text(text: str):
        asyncio.create_task(stream_long(text))

    mock_instance.send_text.side_effect = mock_send_text

    config = {
        "params": {
            "api_key": "k",
            "url": "wss://example.invalid/ws",
            "voice_prompt_id": "v",
        }
    }
    tester = ExtensionTesterFlush()
    tester.set_test_mode_single("deepdub_tts_python", json.dumps(config))
    tester.run()

    assert tester.audio_start_received
    assert tester.first_audio_frame_received
    assert tester.audio_end_received
    assert tester.flush_end_received
    assert not tester.audio_received_after_flush_end
    # The extension must call client.cancel() in response to flush.
    assert mock_instance.cancel.called, "client.cancel() was not invoked"
