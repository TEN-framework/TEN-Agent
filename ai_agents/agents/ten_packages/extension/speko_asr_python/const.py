DUMP_FILE_NAME = "speko_asr_in.pcm"
MODULE_NAME_ASR = "asr"

# Frame types on the Speko router streaming transcription socket.
MSG_TYPE_READY = "ready"
MSG_TYPE_TRANSCRIPT = "transcript"
MSG_TYPE_ERROR = "error"
MSG_TYPE_END = "end"

# Router error codes that a retry cannot fix (configuration problems).
FATAL_ERROR_CODES = {
    "UNSUPPORTED_LANGUAGE",
    "UNSUPPORTED_FEATURE",
    "INVALID_CONFIG",
}
