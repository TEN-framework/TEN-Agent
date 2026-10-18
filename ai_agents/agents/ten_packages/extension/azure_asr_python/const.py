import azure.cognitiveservices.speech as speechsdk

CMD_IN_EVENT = "ten_event"
EVENTTYPE_START = "start"
CMD_PROPERTY_TASK_INFO = "taskInfo"
CMD_PROPERTY_PAYLOAD = "payload"
FINALIZE_MODE_DISCONNECT = "disconnect"
FINALIZE_MODE_MUTE_PKG = "mute_pkg"
DUMP_FILE_NAME = "azure_asr_in.pcm"
STREAM_ID = "stream_id"
REMOTE_USER_ID = "remote_user_id"
MODULE_NAME_ASR = "asr"
AZURE_LANGUAGE_ID_MODE_KEY = "SPEECH-LanguageIdMode"
# AuthenticationFailure and BadRequest are fatal errors that should not be retried
FATAL_ERROR_CODES = [
    speechsdk.CancellationErrorCode.AuthenticationFailure,
    speechsdk.CancellationErrorCode.BadRequest,
]
# Default grace after transport disconnected before ext-level reconnect (overridable via params).
DEFAULT_TRANSPORT_RECONNECT_GRACE_SEC = 10
# Wait for Azure Connection.connected after start_continuous_recognition returns.
DEFAULT_TRANSPORT_HANDSHAKE_TIMEOUT_SEC = 30
# Bounded reconnect ceiling (escalates to FATAL); high enough for long idle / SDK transport cycles.
RECONNECT_MAX_ATTEMPTS = 100
