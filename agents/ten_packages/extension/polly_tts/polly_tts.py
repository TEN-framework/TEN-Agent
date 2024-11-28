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
    engine: str = "generative"
    voice: str = "Matthew" # https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
    sample_rate: int = 16000
    lang_code: str = 'en-US'

class PollyTTS:
    def __init__(self, config: PollyTTSConfig):
        """
        :param config: A PollyConfig
        """

        self.config = config
        self.include_visemes = False
        self.bytes_per_sample = 2
        self.number_of_channels = 1
        self.audio_format = 'pcm'
        if config.access_key and config.secret_key:
            self.client = boto3.client(service_name='polly', 
                                    region_name=config.region,
                                    aws_access_key_id=config.access_key,
                                    aws_secret_access_key=config.secret_key)
        else:
            self.client = boto3.client(service_name='polly', region_name=config.region)

        self.voice_metadata = None
        self.frame_size = int(
            int(config.sample_rate)
            * self.number_of_channels
            * self.bytes_per_sample
            / 100
        )

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
                "OutputFormat": self.audio_format,
                "Text": text,
                "VoiceId": self.config.voice,
            }
            if self.config.lang_code is not None:
                kwargs["LanguageCode"] = self.config.lang_code
            response = self.client.synthesize_speech(**kwargs)
            audio_stream = response["AudioStream"]
            ten_env.log_info("Got audio stream spoken by %s.", self.config.voice)
            visemes = None
            if self.include_visemes:
                kwargs["OutputFormat"] = "json"
                kwargs["SpeechMarkTypes"] = ["viseme"]
                response = self.client.synthesize_speech(**kwargs)
                visemes = [
                    json.loads(v)
                    for v in response["AudioStream"].read().decode().split()
                    if v
                ]
                ten_env.log_info("Got %s visemes.", len(visemes))
        except ClientError:
            ten_env.log_info("Couldn't get audio stream.")
            raise
        else:
            return audio_stream, visemes

    async def get(self, ten_env: AsyncTenEnv, text: str, end_of_segment: bool) -> AsyncIterator[bytes]:
        inputText = text
        if len(inputText) == 0:
             ten_env.log_warning("async_polly_handler: empty input detected.")
        try:
            audio_stream, visemes = self._synthesize(inputText, ten_env)
            with closing(audio_stream) as stream:
                 for chunk in stream.iter_chunks(chunk_size=self.frame_size):
                    if end_of_segment:
                        ten_env.log_info("Streaming complete")
                        self.client = None
                        break

                    yield chunk
        except Exception as e:
            ten_env.log_info(e)
            ten_env.log_info(traceback.format_exc())
