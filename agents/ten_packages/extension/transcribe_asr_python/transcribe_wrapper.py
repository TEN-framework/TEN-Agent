import asyncio

from ten import TenEnv, Data

from amazon_transcribe.auth import StaticCredentialResolver
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import (
    TranscriptEvent,
    TranscriptResultStream,
    StartStreamTranscriptionEventStream,
)

from .transcribe_config import TranscribeConfig

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"

def create_and_send_data(ten: TenEnv, text_result: str, is_final: bool, stream_id: int = 0):
    stable_data = Data.create("text_data")
    stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
    stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text_result)
    stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
    stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final)
    ten.send_data(stable_data)


class AsyncTranscribeWrapper:
    def __init__(
        self,
        config: TranscribeConfig,
        queue: asyncio.Queue,
        ten: TenEnv,
        loop: asyncio.BaseEventLoop,
    ):
        self.queue = queue
        self.ten = ten
        self.stopped = False
        self.config = config
        self.loop = loop
        self.stream = None
        self.handler = None
        self.event_handler_task = None

        if config.access_key and config.secret_key:
            ten.log_info(f"init trascribe client with access key: {config.access_key}")
            self.transcribe_client = TranscribeStreamingClient(
                region=config.region,
                credential_resolver=StaticCredentialResolver(
                    access_key_id=config.access_key, secret_access_key=config.secret_key
                ),
            )
        else:
            ten.log_info(
                "init trascribe client without access key, using default credentials provider chain."
            )

            self.transcribe_client = TranscribeStreamingClient(region=config.region)

        asyncio.set_event_loop(self.loop)
        self.reset_stream()

    def reset_stream(self):
        self.stream = None
        self.handler = None
        self.event_handler_task = None

    async def cleanup(self):
        if self.stream:
            await self.stream.input_stream.end_stream()
            self.ten.log_info("cleanup: stream ended.")

        if self.event_handler_task:
            await self.event_handler_task
            self.ten.log_info("cleanup: event handler ended.")

        self.reset_stream()

    async def create_stream(self, stream_id) -> bool:
        try:
            self.stream = await self.get_transcribe_stream()
            self.handler = TranscribeEventHandler(self.stream.output_stream, self.ten, stream_id)
            self.event_handler_task = asyncio.create_task(self.handler.handle_events())
        except Exception as e:
            self.ten.log_error(str(e))
            return False

        return True

    async def send_frame(self) -> None:
        while not self.stopped:
            try:
                pcm_frame = await asyncio.wait_for(self.queue.get(), timeout=3.0)

                if pcm_frame is None:
                    self.ten.log_warn("send_frame: exit due to None value got.")
                    return

                frame_buf = pcm_frame.get_buf()
                if not frame_buf:
                    self.ten.log_warn("send_frame: empty pcm_frame detected.")
                    continue
                stream_id = pcm_frame.get_property_int("stream_id")
                if not self.stream:
                    self.ten.log_info("lazy init stream.")
                    if not await self.create_stream(stream_id):
                        continue

                await self.stream.input_stream.send_audio_event(audio_chunk=frame_buf)
                self.queue.task_done()
            except asyncio.TimeoutError:
                if self.stream:
                    await self.cleanup()
                    self.ten.log_info(
                        "send_frame: no data for 10s, will close current stream and create a new one when receving new frame."
                    )
                else:
                    self.ten.log_info("send_frame: waiting for pcm frame.")
            except IOError as e:
                self.ten.log_error(f"Error in send_frame: {e}")
            except Exception as e:
                self.ten.log_error(f"Error in send_frame: {e}")
                raise e

        self.ten.log_info("send_frame: exit due to self.stopped == True")

    async def transcribe_loop(self) -> None:
        try:
            await self.send_frame()
        except Exception as e:
            self.ten.log_error(str(e))
        finally:
            await self.cleanup()

    async def get_transcribe_stream(self) -> StartStreamTranscriptionEventStream:
        stream = await self.transcribe_client.start_stream_transcription(
            language_code=self.config.lang_code,
            media_sample_rate_hz=self.config.sample_rate,
            media_encoding=self.config.media_encoding,
        )
        return stream

    def run(self) -> None:
        self.loop.run_until_complete(self.transcribe_loop())
        self.loop.close()
        self.ten.log_info("async_transcribe_wrapper: thread completed.")

    def stop(self) -> None:
        self.stopped = True


class TranscribeEventHandler(TranscriptResultStreamHandler):
    def __init__(self, transcript_result_stream: TranscriptResultStream, ten: TenEnv, stream_id: int = 0):
        super().__init__(transcript_result_stream)
        self.ten = ten
        self.stream_id = stream_id

    async def handle_transcript_event(self, transcript_event: TranscriptEvent) -> None:
        results = transcript_event.transcript.results
        text_result = ""

        is_final = True

        for result in results:
            if result.is_partial:
                is_final = False
                # continue

            for alt in result.alternatives:
                text_result += alt.transcript

        if not text_result:
            return

        self.ten.log_info(f"got transcript: [{text_result}], is_final: [{is_final}]")

        create_and_send_data(ten=self.ten, text_result=text_result, is_final=is_final, stream_id=self.stream_id)
