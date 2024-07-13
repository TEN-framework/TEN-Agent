#
#
# Agora Real Time Engagement
# Created by XinHui Li in 2024-07.
# Copyright (c) 2024 Agora IO. All rights reserved.
#
#

from typing import Iterator
from elevenlabs import Voice, VoiceSettings
from elevenlabs.client import ElevenLabs


class ElevenlabsTTSConfig:
    def __init__(
        self,
        api_key="",
        model_id="eleven_multilingual_v2",
        optimize_streaming_latency=0,
        request_timeout_seconds=30,
        similarity_boost=0.75,
        speaker_boost=False,
        stability=0.5,
        style=0.0,
        voice_id="pNInz6obpgDQGcFmaJgB",
    ) -> None:
        self.api_key = api_key
        self.model_id = model_id
        self.optimize_streaming_latency = optimize_streaming_latency
        self.request_timeout_seconds = request_timeout_seconds
        self.similarity_boost = similarity_boost
        self.speaker_boost = speaker_boost
        self.stability = stability
        self.style = style
        self.voice_id = voice_id


def default_elevenlabs_tts_config() -> ElevenlabsTTSConfig:
    return ElevenlabsTTSConfig()


class ElevenlabsTTS:
    def __init__(self, config: ElevenlabsTTSConfig) -> None:
        self.config = config
        self.client = ElevenLabs(
            api_key=config.api_key, timeout=config.request_timeout_seconds
        )

    def text_to_speech_stream(self, text: str) -> Iterator[bytes]:
        audio_stream = self.client.generate(
            text=text,
            model=self.config.model_id,
            optimize_streaming_latency=self.config.optimize_streaming_latency,
            output_format="pcm_16000",
            stream=True,
            voice=Voice(
                voice_id=self.config.voice_id,
                settings=VoiceSettings(
                    stability=self.config.stability,
                    similarity_boost=self.config.similarity_boost,
                    style=self.config.style,
                    speaker_boost=self.config.speaker_boost,
                ),
            ),
        )

        return audio_stream
