from dataclasses import dataclass
import traceback
import json
from typing import AsyncIterator
from ten.async_ten_env import AsyncTenEnv
from ten_ai_base.config import BaseConfig
import boto3
from botocore.exceptions import ClientError
from contextlib import closing


@dataclass
class PollyTTSConfig(BaseConfig):
    region: str = "us-east-1"
    access_key: str = ""
    secret_key: str = ""
    engine: str = "neural"
    voice: str = (
        "Matthew"  # https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
    )
    sample_rate: int = 16000
    lang_code: str = "en-US"
    bytes_per_sample: int = 2
    include_visemes: bool = False
    number_of_channels: int = 1
    audio_format: str = "pcm"


class PollyTTS:
    def __init__(self, config: PollyTTSConfig, ten_env: AsyncTenEnv) -> None:
        """
        :param config: A PollyConfig
        """
        ten_env.log_info("startinit polly tts")
        self.config = config
        if config.access_key and config.secret_key:
            self.client = boto3.client(
                service_name="polly",
                region_name=config.region,
                aws_access_key_id=config.access_key,
                aws_secret_access_key=config.secret_key,
            )
        else:
            self.client = boto3.client(service_name="polly", region_name=config.region)

        self.voice_metadata = None
        self.frame_size = int(
            int(config.sample_rate)
            * self.config.number_of_channels
            * self.config.bytes_per_sample
            / 100
        )
        self.audio_stream = None

    def _synthesize(self, text, ten_env: AsyncTenEnv):
        """
        Synthesizes speech or speech marks from text, using the specified voice.

        :param text: The text to synthesize.
        :return: The audio stream that contains the synthesized speech and a list
                 of visemes that are associated with the speech audio.
        """
        try:
            kwargs = {
                "Engine": self.config.engine,
                "OutputFormat": self.config.audio_format,
                "Text": text,
                "VoiceId": self.config.voice,
            }
            if self.config.lang_code is not None:
                kwargs["LanguageCode"] = self.config.lang_code
            response = self.client.synthesize_speech(**kwargs)
            audio_stream = response["AudioStream"]
            visemes = None
            if self.config.include_visemes:
                kwargs["OutputFormat"] = "json"
                kwargs["SpeechMarkTypes"] = ["viseme"]
                response = self.client.synthesize_speech(**kwargs)
                visemes = [
                    json.loads(v)
                    for v in response["AudioStream"].read().decode().split()
                    if v
                ]
                ten_env.log_debug("Got %s visemes.", len(visemes))
        except ClientError:
            ten_env.log_error("Couldn't get audio stream.")
            raise
        else:
            return audio_stream, visemes

    async def text_to_speech_stream(
        self, ten_env: AsyncTenEnv, text: str, end_of_segment: bool
    ) -> AsyncIterator[bytes]:
        inputText = text
        if len(inputText) == 0:
            ten_env.log_warning("async_polly_handler: empty input detected.")
        try:
            audio_stream, _ = self._synthesize(inputText, ten_env)
            with closing(audio_stream) as stream:
                for chunk in stream.iter_chunks(chunk_size=self.frame_size):
                    yield chunk
                if end_of_segment:
                    ten_env.log_debug("End of segment reached")
        except Exception:
            ten_env.log_error(traceback.format_exc())

    def on_cancel_tts(self, ten_env: AsyncTenEnv) -> None:
        """
        Cancel ongoing TTS operation
        """
        try:
            if hasattr(self, 'audio_stream') and self.audio_stream:
                self.audio_stream.close()
                self.audio_stream = None
                ten_env.log_debug("TTS cancelled successfully")
        except Exception:
            ten_env.log_error(f"Failed to cancel TTS: {traceback.format_exc()}")
