"""
Constants for the Gradium real-time speech-to-speech translation extension.

Message-type strings confirmed directly by Gradium (2026-08-20) for the
/api/speech/s2s endpoint: setup/ready/audio/text/end_of_stream/error. Note
this differs from gradium_asr_python's protocol -- there is no "vad" event
on this endpoint.
"""

MODULE_NAME_MLLM = "mllm"

WS_MSG_TYPE_SETUP = "setup"
WS_MSG_TYPE_READY = "ready"
WS_MSG_TYPE_AUDIO = "audio"
WS_MSG_TYPE_TEXT = "text"
WS_MSG_TYPE_END = "end_of_stream"
WS_MSG_TYPE_ERROR = "error"

GRADIUM_INPUT_SAMPLE_RATE = 24000
GRADIUM_CHANNELS = 1
GRADIUM_BITS_PER_SAMPLE = 16
