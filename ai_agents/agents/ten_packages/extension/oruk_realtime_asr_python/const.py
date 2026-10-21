DUMP_FILE_NAME = "oruk_realtime_asr_in.pcm"
MODULE_NAME_ASR = "asr"

DEFAULT_URL = "wss://speech-api.oruk.ai/v1/realtime?model=oruk-realtime"
MODEL = "oruk-realtime"
SAMPLE_RATE = 16000

# Realtime event type names.
TRANSCRIPT_PREFIX = "conversation.item.input_audio_transcription."
EMOTION_PREFIX = "conversation.item.input_audio_emotion."
