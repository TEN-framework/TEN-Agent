import asyncio

from ten import (
    TenEnv,
    Data
)

from deepgram import AsyncListenWebSocketClient, DeepgramClientOptions, LiveTranscriptionEvents, LiveOptions

from .log import logger
from .deepgram_config import DeepgramConfig

DATA_OUT_TEXT_DATA_PROPERTY_TEXT = "text"
DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL = "is_final"
DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID = "stream_id"
DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT = "end_of_segment"

def create_and_send_data(ten: TenEnv, text_result: str, is_final: bool, stream_id: int):
    stable_data = Data.create("text_data")
    stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_IS_FINAL, is_final)
    stable_data.set_property_string(DATA_OUT_TEXT_DATA_PROPERTY_TEXT, text_result)
    stable_data.set_property_int(DATA_OUT_TEXT_DATA_PROPERTY_STREAM_ID, stream_id)
    stable_data.set_property_bool(DATA_OUT_TEXT_DATA_PROPERTY_END_OF_SEGMENT, is_final)
    ten.send_data(stable_data)


class AsyncDeepgramWrapper():
    def __init__(self, config: DeepgramConfig, queue: asyncio.Queue, ten:TenEnv, loop: asyncio.BaseEventLoop):
        self.queue = queue
        self.ten = ten
        self.stopped = False
        self.config = config
        self.loop = loop
        self.stream_id = 0

        logger.info(f"init deepgram client with api key: {config.api_key[:5]}")
        self.deepgram_client = AsyncListenWebSocketClient(config=DeepgramClientOptions(
            api_key=config.api_key,
            options={"keepalive": "true"}
        ))

        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.start_listen(ten))

    async def start_listen(self, ten:TenEnv) -> None:
        logger.info(f"start and listen deepgram")

        super = self

        async def on_open(self, open, **kwargs):
            logger.info(f"deepgram event callback on_open: {open}")

        async def on_close(self, close, **kwargs):
            logger.info(f"deepgram event callback on_close: {close}")

        async def on_message(self, result, **kwargs):
            sentence = result.channel.alternatives[0].transcript

            if len(sentence) == 0:
                return

            is_final = result.is_final
            logger.info(f"deepgram got sentence: [{sentence}], is_final: {is_final}, stream_id: {super.stream_id}")

            create_and_send_data(ten=ten, text_result=sentence, is_final=is_final, stream_id=super.stream_id)

        async def on_error(self, error, **kwargs):
            logger.error(f"deepgram event callback on_error: {error}")

        self.deepgram_client.on(LiveTranscriptionEvents.Open, on_open)
        self.deepgram_client.on(LiveTranscriptionEvents.Close, on_close)
        self.deepgram_client.on(LiveTranscriptionEvents.Transcript, on_message)
        self.deepgram_client.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(language=self.config.language,
                              model=self.config.model,
                              sample_rate=self.config.sample_rate,
                              channels=self.config.channels,
                              encoding=self.config.encoding,
                              interim_results=self.config.interim_results,
                              punctuate=self.config.punctuate)
        # connect to websocket
        if await self.deepgram_client.start(options) is False:
            logger.error(f"failed to connect to deepgram")
            return

        logger.info(f"successfully connected to deepgram")

    async def send_frame(self) -> None:
        while not self.stopped:
            try:
                pcm_frame = await asyncio.wait_for(self.queue.get(), timeout=10.0)

                if pcm_frame is None:
                    logger.warning("send_frame: exit due to None value got.")
                    return

                frame_buf = pcm_frame.get_buf()
                if not frame_buf:
                    logger.warning("send_frame: empty pcm_frame detected.")
                    continue

                self.stream_id = pcm_frame.get_property_int('stream_id')
                await self.deepgram_client.send(frame_buf)
                self.queue.task_done()
            except asyncio.TimeoutError as e:
                logger.exception(f"error in send_frame: {e}")
            except IOError as e:
                logger.exception(f"error in send_frame: {e}")
            except Exception as e:
                logger.exception(f"error in send_frame: {e}")
                raise e

        logger.info("send_frame: exit due to self.stopped == True")

    async def deepgram_loop(self) -> None:
        try:
            await self.send_frame()
        except Exception as e:
            logger.exception(e)

    def run(self) -> None:
        self.loop.run_until_complete(self.deepgram_loop())
        self.loop.close()
        logger.info("async_deepgram_wrapper: thread completed.")

    def stop(self) -> None:
        self.stopped = True
