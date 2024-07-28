import io
import json
import logging
import boto3
from typing import Union
from botocore.exceptions import ClientError

from .log import logger

# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/polly/client/synthesize_speech.html
class PollyConfig:
    def __init__(self, 
            region: str, 
            access_key: str, 
            secret_key: str, 
            voice: str, 
            engine: str,        # 'standard'|'neural'|'long-form'|'generative'
            sample_rate: Union[str, int],
            lang_code: None):   # only necessary if using a bilingual voice
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key

        self.voice = voice
        self.engine = engine
        self.lang_code = lang_code
        self.sample_rate = str(sample_rate)

        self.speech_mark_type = 'sentence' # 'sentence'|'ssml'|'viseme'|'word'
        self.audio_format = 'pcm' # 'json'|'mp3'|'ogg_vorbis'|'pcm'
        self.include_visemes = False

    @classmethod
    def default_config(cls):
        return cls(
            region="us-east-1",
            access_key="",
            secret_key="",
            engine="generative",
            voice="Matthew", # https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
            sample_rate=16000,
            lang_code='en-US'
        )


class PollyWrapper:
    """Encapsulates Amazon Polly functions."""

    def __init__(self, config: PollyConfig):
        """
        :param config: A PollyConfig
        """

        self.config = config

        if config.access_key and config.secret_key:
            logger.info(f"BedrockLLM initialized with access key: {config.access_key}")

            self.client = boto3.client(service_name='polly', 
                                    region_name=config.region,
                                    aws_access_key_id=config.access_key,
                                    aws_secret_access_key=config.secret_key)
        else:
            logger.info(f"BedrockLLM initialized without access key, using default credentials provider chain.")
            self.client = boto3.client(service_name='polly', region_name=config.region)

        self.voice_metadata = None


    def describe_voices(self):
        """
        Gets metadata about available voices.

        :return: The list of voice metadata.
        """
        try:
            response = self.client.describe_voices()
            self.voice_metadata = response["Voices"]
            logger.info("Got metadata about %s voices.", len(self.voice_metadata))
        except ClientError:
            logger.exception("Couldn't get voice metadata.")
            raise
        else:
            return self.voice_metadata


    def synthesize(self, text):
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
            logger.info("Got audio stream spoken by %s.", self.config.voice)
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
                logger.info("Got %s visemes.", len(visemes))
        except ClientError:
            logger.exception("Couldn't get audio stream.")
            raise
        else:
            return audio_stream, visemes

    def get_voice_engines(self):
        """
        Extracts the set of available voice engine types from the full list of
        voice metadata.

        :return: The set of voice engine types.
        """
        if self.voice_metadata is None:
            self.describe_voices()

        engines = set()
        for voice in self.voice_metadata:
            for engine in voice["SupportedEngines"]:
                engines.add(engine)
        return engines


    def get_languages(self, engine):
        """
        Extracts the set of available languages for the specified engine from the
        full list of voice metadata.

        :param engine: The engine type to filter on.
        :return: The set of languages available for the specified engine type.
        """
        if self.voice_metadata is None:
            self.describe_voices()

        return {
            vo["LanguageName"]: vo["LanguageCode"]
            for vo in self.voice_metadata
            if engine in vo["SupportedEngines"]
        }


    def get_voices(self, engine, language_code):
        """
        Extracts the set of voices that are available for the specified engine type
        and language from the full list of voice metadata.

        :param engine: The engine type to filter on.
        :param language_code: The language to filter on.
        :return: The set of voices available for the specified engine type and language.
        """
        if self.voice_metadata is None:
            self.describe_voices()

        return {
            vo["Name"]: vo["Id"]
            for vo in self.voice_metadata
            if engine in vo["SupportedEngines"] and language_code == vo["LanguageCode"]
        }