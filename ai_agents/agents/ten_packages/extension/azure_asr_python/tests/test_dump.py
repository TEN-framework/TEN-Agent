import asyncio
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import uuid
from typing_extensions import override
from ten_runtime import (
    AsyncExtensionTester,
    AsyncTenEnvTester,
    Data,
    AudioFrame,
    TenError,
    TenErrorCode,
)
import json

# We must import it, which means this test fixture will be automatically executed
from .mock import patch_azure_ws, trigger_vendor_live  # noqa: F401


class AzureAsrExtensionTester(AsyncExtensionTester):

    def __init__(self):
        super().__init__()
        self.sender_task: asyncio.Task[None] | None = None

    async def audio_sender(self, ten_env: AsyncTenEnvTester):
        # total send 30 frames
        for i in range(30):
            byte1 = i % 256
            byte2 = (i + 1) % 256
            chunk = (
                bytes([byte1, byte2]) * 160
            )  # 320 bytes (16-bit * 160 samples)
            if not chunk:
                break
            audio_frame = AudioFrame.create("pcm_frame")
            metadata = {"session_id": "123"}
            audio_frame.set_property_from_json("metadata", json.dumps(metadata))
            audio_frame.alloc_buf(len(chunk))
            buf = audio_frame.lock_buf()
            buf[:] = chunk
            audio_frame.unlock_buf(buf)
            await ten_env.send_audio_frame(audio_frame)
            await asyncio.sleep(0.1)

        # Wait for 1 second and stop test.
        await asyncio.sleep(1)
        ten_env.stop_test()

    @override
    async def on_start(self, ten_env_tester: AsyncTenEnvTester) -> None:
        self.sender_task = asyncio.create_task(
            self.audio_sender(ten_env_tester)
        )

    @override
    async def on_stop(self, ten_env_tester: AsyncTenEnvTester) -> None:
        if self.sender_task:
            _ = self.sender_task.cancel()
            try:
                await self.sender_task
            except asyncio.CancelledError:
                pass


def test_dump(patch_azure_ws):
    def fake_start_continuous_recognition():
        def triggerSessionStarted():
            trigger_vendor_live(patch_azure_ws.event_handlers, session_id="123")

        threading.Timer(0.4, triggerSessionStarted).start()
        return None

    def fake_stop_continuous_recognition():
        return None

    # Inject into recognizer
    patch_azure_ws.recognizer_instance.start_continuous_recognition.side_effect = (
        fake_start_continuous_recognition
    )

    patch_azure_ws.recognizer_instance.stop_continuous_recognition.side_effect = (
        fake_stop_continuous_recognition
    )

    # random a dir
    temp_dir = Path(tempfile.gettempdir()) / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)

    property_json = {
        "params": {
            "key": "fake_key",
            "region": "fake_region",
            "dump": True,
            "dump_path": str(temp_dir),
        }
    }

    tester = AzureAsrExtensionTester()
    tester.set_test_mode_single("azure_asr_python", json.dumps(property_json))
    err = tester.run()
    assert err is None, f"test_asr_result err: {err}"

    # Find any .pcm file in the dump directory
    pcm_files = list(temp_dir.glob("*.pcm"))
    assert (
        len(pcm_files) > 0
    ), f"No .pcm files found in dump directory: {temp_dir}"

    # Use the first .pcm file found
    dump_file = pcm_files[0]
    print(f"Found dump file: {dump_file}")

    # Check the dump file content
    with open(dump_file, "rb") as f:
        content = f.read()
        assert len(content) == 30 * 320

        # Verify each frame in the dump file
        for i in range(30):
            byte1 = i % 256
            byte2 = (i + 1) % 256
            expected_chunk = bytes([byte1, byte2]) * 160  # 320 bytes
            actual_chunk = content[i * 320 : (i + 1) * 320]
            assert (
                actual_chunk == expected_chunk
            ), f"Frame {i} mismatch: expected {expected_chunk[:10]}..., got {actual_chunk[:10]}..."
