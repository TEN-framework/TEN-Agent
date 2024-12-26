from ten import (
    Extension,
    TenEnv,
    Cmd,
    AudioFrame,
    StatusCode,
    CmdResult,
)

import asyncio
import threading

from .transcribe_wrapper import AsyncTranscribeWrapper, TranscribeConfig

PROPERTY_REGION = "region"  # Optional
PROPERTY_ACCESS_KEY = "access_key"  # Optional
PROPERTY_SECRET_KEY = "secret_key"  # Optional
PROPERTY_SAMPLE_RATE = "sample_rate"  # Optional
PROPERTY_LANG_CODE = "lang_code"  # Optional


class TranscribeAsrExtension(Extension):
    def __init__(self, name: str):
        super().__init__(name)

        self.stopped = False
        self.queue = asyncio.Queue(maxsize=3000)  # about 3000 * 10ms = 30s input
        self.transcribe = None
        self.thread = None

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def on_start(self, ten: TenEnv) -> None:
        ten.log_info("TranscribeAsrExtension on_start")

        transcribe_config = TranscribeConfig.default_config()

        for optional_param in [
            PROPERTY_REGION,
            PROPERTY_SAMPLE_RATE,
            PROPERTY_LANG_CODE,
            PROPERTY_ACCESS_KEY,
            PROPERTY_SECRET_KEY,
        ]:
            try:
                value = ten.get_property_string(optional_param).strip()
                if value:
                    transcribe_config.__setattr__(optional_param, value)
            except Exception as err:
                ten.log_debug(
                    f"GetProperty optional {optional_param} failed, err: {err}. Using default value: {transcribe_config.__getattribute__(optional_param)}"
                )

        self.transcribe = AsyncTranscribeWrapper(
            transcribe_config, self.queue, ten, self.loop
        )

        ten.log_info("Starting async_transcribe_wrapper thread")
        self.thread = threading.Thread(target=self.transcribe.run, args=[])
        self.thread.start()

        ten.on_start_done()

    def put_pcm_frame(self, ten: TenEnv, pcm_frame: AudioFrame) -> None:
        try:
            asyncio.run_coroutine_threadsafe(
                self.queue.put(pcm_frame), self.loop
            ).result(timeout=0.1)
        except asyncio.QueueFull:
            ten.log_error("Queue is full, dropping frame")
        except Exception as e:
            ten.log_error(f"Error putting frame in queue: {e}")

    def on_audio_frame(self, ten: TenEnv, frame: AudioFrame) -> None:
        self.put_pcm_frame(ten, pcm_frame=frame)

    def on_stop(self, ten: TenEnv) -> None:
        ten.log_info("TranscribeAsrExtension on_stop")

        # put an empty frame to stop transcribe_wrapper
        self.put_pcm_frame(ten, None)
        self.stopped = True
        self.thread.join()
        self.loop.stop()
        self.loop.close()

        ten.on_stop_done()

    def on_cmd(self, ten: TenEnv, cmd: Cmd) -> None:
        ten.log_info("TranscribeAsrExtension on_cmd")
        cmd_json = cmd.to_json()
        ten.log_info(f"TranscribeAsrExtension on_cmd json: {cmd_json}")

        cmdName = cmd.get_name()
        ten.log_info(f"got cmd {cmdName}")

        cmd_result = CmdResult.create(StatusCode.OK)
        cmd_result.set_property_string("detail", "success")
        ten.return_result(cmd_result, cmd)
