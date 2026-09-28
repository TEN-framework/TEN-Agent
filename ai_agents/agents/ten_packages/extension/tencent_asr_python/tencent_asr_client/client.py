import asyncio
import json
from typing import Any, Callable
from typing_extensions import override
import logging
from .log import get_logger
from .ws_client import WebSocketClient
from .schemas import RequestParams, ResponseData, RecoginizeResult


class AsyncTencentAsrListener:
    async def on_asr_start(self, response: ResponseData):
        pass

    async def on_asr_fail(self, response: ResponseData):
        """
        response.result is tencent asr server error.
        """

    async def on_asr_error(
        self, response: ResponseData[str], error: Exception | None = None
    ):
        """
        response.code: 9999 is TencentAsrClient error, 9998 is WebSocketClient error.
        response.message = "error"
        response.voice_id is the voice_id of the request.
        response.result is the Exception instance.
        """

    async def on_asr_sentence_start(
        self, response: ResponseData[RecoginizeResult]
    ):
        """
        response.result is the RecoginizeResult instance.
        response.result.slice_type is SliceType.START.
        """

    async def on_asr_sentence_change(
        self, response: ResponseData[RecoginizeResult]
    ):
        """
        response.result is the RecoginizeResult instance.
        response.result.slice_type is SliceType.PROCESSING.
        """

    async def on_asr_sentence_end(
        self, response: ResponseData[RecoginizeResult]
    ):
        """
        response.result is the RecoginizeResult instance.
        response.result.slice_type is SliceType.END.
        """

    async def on_asr_complete(self, response: ResponseData[RecoginizeResult]):
        """
        response.final is True.
        """

    async def on_asr_close(self, code: int, reason: str):
        """Called when the websocket connection is closed."""


class TencentAsrListener:
    def on_asr_start(self, response: ResponseData):
        pass

    def on_asr_fail(self, response: ResponseData):
        pass

    def on_asr_error(
        self, response: ResponseData[str], error: Exception | None = None
    ):
        pass

    def on_asr_sentence_start(self, response: ResponseData[RecoginizeResult]):
        pass

    def on_asr_sentence_change(self, response: ResponseData[RecoginizeResult]):
        pass

    def on_asr_sentence_end(self, response: ResponseData[RecoginizeResult]):
        pass

    def on_asr_complete(self, response: ResponseData[RecoginizeResult]):
        pass

    def on_asr_close(self, code: int, reason: str):
        pass


class TencentAsrClient(WebSocketClient):
    def __init__(
        self,
        params: RequestParams,
        logger: logging.Logger | None = None,
        log_level: str = "INFO",
        log_path: str | None = None,
        listener: TencentAsrListener | AsyncTencentAsrListener | None = None,
        **kwargs,
    ):
        if logger is None:
            self.logger = get_logger(level=log_level, log_path=log_path)
        else:
            self.logger = logger

        if listener is None:
            self._listener = AsyncTencentAsrListener()
        else:
            self._listener = listener

        self._params = params
        uri = self._params.uri()

        super().__init__(uri, logger=self.logger, **kwargs)

    async def _call_listener(self, func: Callable, *args, **kwargs):
        # awaitable function
        if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            func(*args, **kwargs)

    @override
    async def on_open(self):
        response = ResponseData(
            code=0, message="success", voice_id=self._params.voice_id
        )
        self.logger.info(f"✅ Connection opened. voice_id: {response.voice_id}")
        await self._call_listener(self._listener.on_asr_start, response)

    @override
    async def on_message(self, message: str | bytes):
        self.logger.info("Received ASR message: length=%d", len(message))
        try:
            response = ResponseData[Any].model_validate_json(message)
        except Exception as e:
            self.logger.error(
                "Failed to parse ASR message: error_type=%s", type(e).__name__
            )
            response = ResponseData[str](
                code=9999,
                message="error",
                voice_id=self._params.voice_id,
                result=str(e),
            )
            await self._call_listener(self._listener.on_asr_error, response, e)
            return

        if response.voice_id is None:
            response.voice_id = self._params.voice_id

        if response.code != 0:
            self.logger.error("ASR server error: code=%s", response.code)
            await self._call_listener(self._listener.on_asr_fail, response)
            return

        # code, message, voice_id, message_id, result, final
        # result should be RecoginizeResult instance.
        try:
            response = ResponseData[RecoginizeResult].model_validate_json(
                message
            )
        except Exception as e:
            self.logger.error(
                "Failed to parse ASR result: error_type=%s", type(e).__name__
            )
            response = ResponseData[str](
                code=9999,
                message="error",
                voice_id=self._params.voice_id,
                result=str(e),
            )
            await self._call_listener(self._listener.on_asr_error, response, e)
            return
        self.logger.info(
            "ASR response: code=%s, voice_id=%s, final=%s",
            response.code,
            response.voice_id,
            response.final,
        )
        if response.final:
            await self._call_listener(self._listener.on_asr_complete, response)
            return
        if response.result is None:
            return
        if response.result.slice_type == RecoginizeResult.SliceType.START:
            await self._call_listener(
                self._listener.on_asr_sentence_start, response
            )
        elif (
            response.result.slice_type == RecoginizeResult.SliceType.PROCESSING
        ):
            await self._call_listener(
                self._listener.on_asr_sentence_change, response
            )
        elif response.result.slice_type == RecoginizeResult.SliceType.END:
            await self._call_listener(
                self._listener.on_asr_sentence_end, response
            )

    @override
    async def on_close(self, code: int, reason: str):
        self.logger.warning(
            f"🔴 Connection closed. Code: {code}, Reason: {reason}"
        )
        await self._call_listener(self._listener.on_asr_close, code, reason)

    @override
    async def on_error(self, error: Exception):
        self.logger.error("ASR client error: error_type=%s", type(error).__name__)
        response = ResponseData[str](
            code=9998,
            message="error",
            voice_id=self._params.voice_id,
            result=str(error),
        )
        await self._call_listener(self._listener.on_asr_error, response, error)

    @override
    async def on_reconnect(self):
        self.logger.info("🔄 Reconnected to the server.")
        self._uri = self._params.uri()

    def update_params(self, params: RequestParams) -> None:
        """Update request parameters for the next connection."""
        self._params = params

    async def send_pcm_data(self, data: bytes):
        assert (
            self._params.voice_format == RequestParams.VoiceFormat.PCM
        ), "the params.voice_format is not PCM"
        await self.send(data)

    async def send_end_of_stream(self):
        await self.send(json.dumps({"type": "end"}))
        # await self.stop()

    async def send_heartbeat(self):
        await self.send(b"")


if __name__ == "__main__":
    from pathlib import Path
    import os

    async def send_audio_data(client: TencentAsrClient):
        with open(
            Path(__file__).parent.parent
            / "tests/test_data/16k_en_us_helloworld.pcm",
            "rb",
        ) as f:
            print("start sending audio data")
            sample_rate = 16000
            total_ms = 10000
            chunk_time_ms = 50
            chunk_size = int(chunk_time_ms * sample_rate / 1000 * 2)
            cnt = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    await client.send_end_of_stream()
                    break
                await client.send_pcm_data(chunk)
                await asyncio.sleep(chunk_time_ms / 1000)
                cnt += chunk_time_ms
                print(f"sent {cnt}ms")
                if cnt > total_ms:
                    await client.send_end_of_stream()
                    break

    async def main():
        params = RequestParams(
            appid=os.getenv("TENCENT_ASR_APP_ID", ""),
            secretkey=os.getenv("TENCENT_ASR_SECRET_KEY", ""),
            secretid=os.getenv("TENCENT_ASR_SECRET_ID", ""),
            engine_model_type="16k_en",
            voice_format=RequestParams.VoiceFormat.PCM,
            word_info=2,
            needvad=1,
            vad_silence_time=1000,
        )
        client = TencentAsrClient(
            params=params,
            log_level="DEBUG",
            auto_reconnect=True,
        )
        logger = client.logger

        try:
            asyncio.create_task(client.start())
            await send_audio_data(client)
            await asyncio.sleep(2)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            logger.info("Main is shutting down the clientpass")
            await client.stop()

    asyncio.run(main())
