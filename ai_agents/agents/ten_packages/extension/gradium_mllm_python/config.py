"""
Configuration for the Gradium real-time speech-to-speech translation
(MLLM) extension.

Field names and the region/base_url resolution logic mirror
gradium_asr_python/config.py and gradium_tts_python/config.py -- those two
extensions are already wired up against Gradium's real ASR and TTS
websocket APIs (wss://<region>.api.gradium.ai/api/speech/{asr,tts}).

The combined speech-to-speech endpoint's protocol was confirmed directly by
Gradium (Pratim, 2026-08-20):
  - path: /api/speech/s2s
  - the existing GRADIUM_API_KEY covers this endpoint too
  - setup payload: model_name="s2s-translate", stt_model_name="stt-translate",
    tts_model_name="default", input_format/output_format="pcm" (24kHz in,
    48kHz out), voice_id, and json_config={"target_language": ...} --
    target_language is NOT a top-level field, it nests inside json_config.
  - "text" messages carry translated output only (no separate
    source-language transcript).
  - "vad" is not part of this protocol; only ready/audio/text/end_of_stream/
    error are ever sent.
  - voice_id MUST be a voice belonging to target_language, or Gradium will
    reject/mis-synthesize -- there's no validation for this below, since it
    depends on Gradium's voice catalog per language.
"""

from typing import Any, Literal

from pydantic import BaseModel


class GradiumMLLMConfig(BaseModel):
    api_key: str = ""
    """API key for Gradium API authentication (sent as the x-api-key header)."""

    region: Literal["eu", "us"] = "us"
    """Gradium API region. Options: 'eu' (Europe) or 'us' (USA)."""

    base_url: str = ""
    """Optional explicit override of the websocket host (skips region-based lookup)."""

    path: str = "/api/speech/s2s"
    """Websocket path for the speech-to-speech endpoint."""

    model_name: str = "s2s-translate"
    """Name of the Gradium speech-to-speech model to use."""

    stt_model_name: str = "stt-translate"
    """Model used for the ASR leg of the pipeline."""

    tts_model_name: str = "default"
    """Model used for the TTS leg of the pipeline."""

    voice_id: str = ""
    """Voice used for the synthesized (translated) speech output. Must belong to target_language."""

    target_language: str = "en"
    """Language to translate into (en, fr, de, es, pt confirmed supported). Sent nested in json_config."""

    input_format: str = "pcm"
    """Audio input format, matching gradium_asr_python's convention."""

    output_format: str = "pcm"
    """Audio output format, matching gradium_tts_python's convention."""

    input_sample_rate: int = 24000
    """Audio sample rate (Hz) Gradium expects for input PCM."""

    dump: bool = False
    """Enable audio dumping for debugging."""

    dump_path: str = "/tmp"
    """Path to dump audio files when debugging."""

    def websocket_url(self) -> str:
        """Build the websocket URL based on region, or an explicit base_url override."""
        if self.base_url:
            return f"{self.base_url}{self.path}"
        region = self.region if self.region in ("us", "eu") else "us"
        return f"wss://{region}.api.gradium.ai{self.path}"

    def output_sample_rate(self) -> int:
        """Return sample rate based on output_format, matching gradium_tts_python's convention."""
        fmt = self.output_format.lower()
        if fmt == "pcm_16000":
            return 16000
        if fmt == "pcm_24000":
            return 24000
        return 48000

    def setup_message(self) -> dict[str, Any]:
        """
        'setup' payload for the speech-to-speech session, per Gradium's
        confirmed shape. target_language nests inside json_config -- it is
        NOT a top-level field.
        """
        return {
            "type": "setup",
            "model_name": self.model_name,
            "stt_model_name": self.stt_model_name,
            "tts_model_name": self.tts_model_name,
            "input_format": self.input_format,
            "output_format": self.output_format,
            "voice_id": self.voice_id,
            "json_config": {"target_language": self.target_language},
        }
