import json

from dataclasses import dataclass, asdict, field, is_dataclass
from typing import Any, Dict, Literal, Optional, List, Set, Union
from enum import Enum
import uuid


def generate_event_id() -> str:
    return str(uuid.uuid4())


class AudioFormats(str, Enum):
    WAV24 = "wav24"
    PCM = "pcm"
    G711_ULAW = "g711_ulaw"
    G711_ALAW = "g711_alaw"


class ItemType(str, Enum):
    Message = "message"
    FunctionCall = "function_call"
    FunctionCallOutput = "function_call_output"


class MessageRole(str, Enum):
    System = "system"
    User = "user"
    Assistant = "assistant"


class ContentType(str, Enum):
    InputText = "input_text"
    InputAudio = "input_audio"
    Text = "text"
    Audio = "audio"


class ChatMode(str, Enum):
    VideoPassive = "video_passive"
    Audio = "audio"


@dataclass
class FunctionToolChoice:
    name: str  # Name of the function
    type: str = "function"  # Fixed value for type


# ToolChoice can be either a literal string or FunctionToolChoice
ToolChoice = Union[
    str, FunctionToolChoice
]  # "none", "auto", "required", or FunctionToolChoice


@dataclass
class RealtimeError:
    type: str  # The type of the error
    message: str  # The error message
    code: Optional[str] = None  # Optional error code
    param: Optional[str] = None  # Optional parameter related to the error
    event_id: Optional[str] = None  # Optional event ID for tracing


@dataclass
class InputAudioTranscription:
    model: str = "whisper-1"  # Default transcription model is "whisper-1"


@dataclass
class ServerVADUpdateParams:
    threshold: Optional[float] = None  # Threshold for voice activity detection
    prefix_padding_ms: Optional[int] = (
        None  # Amount of padding before the voice starts (in milliseconds)
    )
    silence_duration_ms: Optional[int] = (
        None  # Duration of silence before considering speech stopped (in milliseconds)
    )
    type: str = "server_vad"  # Fixed value for VAD type


@dataclass
class BetaFieldsParams:
    chat_mode: ChatMode = (
        ChatMode.Audio
    )  # Chat mode for the session, defaulting to "audio"
    tts_source: Optional[str] = "e2e"  # Source of the TTS audio


@dataclass
class Session:
    id: str  # The unique identifier for the session
    model: str  # The model associated with the session (e.g., "gpt-3")
    # expires_at: int  # Expiration time of the session in seconds since the epoch (UNIX timestamp)
    object: str = "realtime.session"  # Fixed value indicating the object type
    modalities: Set[str] = field(
        default_factory=lambda: {"text", "audio"}
    )  # Set of allowed modalities (e.g., "text", "audio")
    instructions: Optional[str] = None  # Instructions or guidance for the session
    turn_detection: Optional[ServerVADUpdateParams] = (
        None  # Voice activity detection (VAD) settings
    )
    input_audio_format: AudioFormats = (
        AudioFormats.PCM
    )  # Audio format for input (e.g., "pcm16")
    output_audio_format: AudioFormats = (
        AudioFormats.PCM
    )  # Audio format for output (e.g., "pcm16")
    input_audio_transcription: Optional[InputAudioTranscription] = (
        None  # Audio transcription model settings (e.g., "whisper-1")
    )
    tools: List[Dict[str, Union[str, Any]]] = field(
        default_factory=list
    )  # List of tools available during the session
    tool_choice: Literal["auto", "none", "required"] = (
        "auto"  # How tools should be used in the session
    )
    temperature: float = 0.8  # Temperature setting for model creativity
    max_response_output_tokens: Union[int, Literal["inf"]] = (
        "inf"  # Maximum number of tokens in the response, or "inf" for unlimited
    )


@dataclass
class SessionUpdateParams:
    # model: Optional[str] = None  # Optional string to specify the model
    # modalities: Optional[Set[str]] = None  # Set of allowed modalities (e.g., "text", "audio")
    instructions: Optional[str] = None  # Optional instructions string
    # voice: Optional[Voices] = None  # Voice selection, can be `None` or from `Voices` Enum
    turn_detection: ServerVADUpdateParams = field(
        default_factory=ServerVADUpdateParams
    )  # VAD update parameters
    input_audio_format: Optional[AudioFormats] = (
        None  # Input audio format from `AudioFormats` Enum
    )
    output_audio_format: Optional[AudioFormats] = (
        None  # Output audio format from `AudioFormats` Enum
    )
    # input_audio_transcription: Optional[InputAudioTranscription] = None  # Optional transcription model
    tools: Optional[List[Dict[str, Union[str, any]]]] = (
        None  # List of tools (e.g., dictionaries)
    )
    # tool_choice: Optional[ToolChoice] = None  # ToolChoice, either string or `FunctionToolChoice`
    # temperature: Optional[float] = None  # Optional temperature for response generation
    # max_response_output_tokens: Optional[Union[int, str]] = None  # Max response tokens, "inf" for infinite
    beta_fields: BetaFieldsParams = field(
        default_factory=BetaFieldsParams
    )  # Beta fields for additional settings


# Define individual message item param types
@dataclass
class SystemMessageItemParam:
    content: List[dict]  # This can be more specific based on content structure
    id: Optional[str] = None
    status: Optional[str] = None
    type: str = "message"
    role: str = "system"


@dataclass
class UserMessageItemParam:
    content: List[dict]  # Similarly, content can be more specific
    id: Optional[str] = None
    status: Optional[str] = None
    type: str = "message"
    role: str = "user"


@dataclass
class AssistantMessageItemParam:
    content: List[dict]  # Content structure here depends on your schema
    id: Optional[str] = None
    status: Optional[str] = None
    type: str = "message"
    role: str = "assistant"


@dataclass
class FunctionCallItemParam:
    name: str
    call_id: str
    arguments: str
    type: str = "function_call"
    id: Optional[str] = None
    status: Optional[str] = None


@dataclass
class FunctionCallOutputItemParam:
    # call_id: str
    output: str
    id: Optional[str] = None
    type: str = "function_call_output"


# Union of all possible item types
ItemParam = Union[
    SystemMessageItemParam,
    UserMessageItemParam,
    AssistantMessageItemParam,
    FunctionCallItemParam,
    FunctionCallOutputItemParam,
]


# Assuming the EventType and other enums are already defined
# For reference:
class EventType(str, Enum):
    SESSION_UPDATE = "session.update"
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    INPUT_AUDIO_BUFFER_COMMIT = "input_audio_buffer.commit"
    INPUT_AUDIO_BUFFER_CLEAR = "input_audio_buffer.clear"
    UPDATE_CONVERSATION_CONFIG = "update_conversation_config"
    ITEM_CREATE = "conversation.item.create"
    ITEM_TRUNCATE = "conversation.item.truncate"
    ITEM_DELETE = "conversation.item.delete"
    RESPONSE_CREATE = "response.create"
    RESPONSE_CANCEL = "response.cancel"

    ERROR = "error"
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"

    INPUT_AUDIO_BUFFER_COMMITTED = "input_audio_buffer.committed"
    INPUT_AUDIO_BUFFER_CLEARED = "input_audio_buffer.cleared"
    INPUT_AUDIO_BUFFER_SPEECH_STARTED = "input_audio_buffer.speech_started"
    INPUT_AUDIO_BUFFER_SPEECH_STOPPED = "input_audio_buffer.speech_stopped"

    ITEM_CREATED = "conversation.item.created"
    ITEM_DELETED = "conversation.item.deleted"
    ITEM_TRUNCATED = "conversation.item.truncated"
    ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED = (
        "conversation.item.input_audio_transcription.completed"
    )
    ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED = (
        "conversation.item.input_audio_transcription.failed"
    )

    RESPONSE_CREATED = "response.created"
    RESPONSE_CANCELLED = "response.cancelled"
    RESPONSE_DONE = "response.done"
    RESPONSE_OUTPUT_ITEM_ADDED = "response.output_item.added"
    RESPONSE_OUTPUT_ITEM_DONE = "response.output_item.done"
    RESPONSE_CONTENT_PART_ADDED = "response.content_part.added"
    RESPONSE_CONTENT_PART_DONE = "response.content_part.done"
    RESPONSE_TEXT_DELTA = "response.text.delta"
    RESPONSE_TEXT_DONE = "response.text.done"
    RESPONSE_AUDIO_TRANSCRIPT_DELTA = "response.audio_transcript.delta"
    RESPONSE_AUDIO_TRANSCRIPT_DONE = "response.audio_transcript.done"
    RESPONSE_AUDIO_DELTA = "response.audio.delta"
    RESPONSE_AUDIO_DONE = "response.audio.done"
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA = "response.function_call_arguments.delta"
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE = "response.function_call_arguments.done"
    RATE_LIMITS_UPDATED = "rate_limits.updated"


# Base class for all ServerToClientMessages
@dataclass
class ServerToClientMessage:
    event_id: str


@dataclass
class ErrorMessage(ServerToClientMessage):
    error: RealtimeError
    type: str = EventType.ERROR


@dataclass
class SessionCreated(ServerToClientMessage):
    session: Session
    type: str = EventType.SESSION_CREATED


@dataclass
class SessionUpdated(ServerToClientMessage):
    session: Session
    type: str = EventType.SESSION_UPDATED


@dataclass
class InputAudioBufferCommitted(ServerToClientMessage):
    item_id: str
    type: str = EventType.INPUT_AUDIO_BUFFER_COMMITTED
    previous_item_id: Optional[str] = None


@dataclass
class InputAudioBufferCleared(ServerToClientMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_CLEARED


@dataclass
class InputAudioBufferSpeechStarted(ServerToClientMessage):
    audio_start_ms: int
    # item_id: str
    type: str = EventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED


@dataclass
class InputAudioBufferSpeechStopped(ServerToClientMessage):
    audio_end_ms: int
    type: str = EventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED
    # item_id: Optional[str] = None


@dataclass
class ItemCreated(ServerToClientMessage):
    item: ItemParam
    type: str = EventType.ITEM_CREATED
    previous_item_id: Optional[str] = None


@dataclass
class ItemTruncated(ServerToClientMessage):
    item_id: str
    content_index: int
    audio_end_ms: int
    type: str = EventType.ITEM_TRUNCATED


@dataclass
class ItemDeleted(ServerToClientMessage):
    item_id: str
    type: str = EventType.ITEM_DELETED


# Assuming the necessary enums, ItemParam, and other classes are defined above
# ResponseStatus could be a string or an enum, depending on your schema

# Enum or Literal for ResponseStatus (could be more extensive)
ResponseStatus = Union[
    str, Literal["in_progress", "completed", "cancelled", "incomplete", "failed"]
]


# Define status detail classes
@dataclass
class ResponseCancelledDetails:
    reason: str  # e.g., "turn_detected", "client_cancelled"
    type: str = "cancelled"


@dataclass
class ResponseIncompleteDetails:
    reason: str  # e.g., "max_output_tokens", "content_filter"
    type: str = "incomplete"


@dataclass
class ResponseError:
    type: str  # The type of the error, e.g., "validation_error", "server_error"
    message: str  # The error message describing what went wrong
    code: Optional[str] = (
        None  # Optional error code, e.g., HTTP status code, API error code
    )


@dataclass
class ResponseFailedDetails:
    error: ResponseError  # Assuming ResponseError is already defined
    type: str = "failed"


# Union of possible status details
ResponseStatusDetails = Union[
    ResponseCancelledDetails, ResponseIncompleteDetails, ResponseFailedDetails
]


# Define Usage class to handle token usage
@dataclass
class InputTokenDetails:
    cached_tokens: int
    text_tokens: int
    audio_tokens: int


@dataclass
class OutputTokenDetails:
    text_tokens: int
    audio_tokens: int


@dataclass
class Usage:
    total_tokens: int
    input_tokens: int
    output_tokens: int
    input_token_details: InputTokenDetails
    output_token_details: OutputTokenDetails


# The Response dataclass definition
@dataclass
class Response:
    id: str  # Unique ID for the response
    output: List[ItemParam] = field(
        default_factory=list
    )  # List of items in the response
    object: str = "realtime.response"  # Fixed value for object type
    status: ResponseStatus = "in_progress"  # Status of the response
    status_details: Optional[ResponseStatusDetails] = (
        None  # Additional details based on status
    )
    usage: Optional[Usage] = None  # Token usage information
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata for the response


@dataclass
class ResponseCreated(ServerToClientMessage):
    response: Response
    type: str = EventType.RESPONSE_CREATED


@dataclass
class ResponseDone(ServerToClientMessage):
    response: Response
    type: str = EventType.RESPONSE_DONE


@dataclass
class ResponseTextDelta(ServerToClientMessage):
    output_index: int
    content_index: int
    delta: str
    type: str = EventType.RESPONSE_TEXT_DELTA


@dataclass
class ResponseTextDone(ServerToClientMessage):
    output_index: int
    content_index: int
    text: str
    type: str = EventType.RESPONSE_TEXT_DONE


@dataclass
class ResponseAudioTranscriptDelta(ServerToClientMessage):
    response_id: str
    output_index: int
    content_index: int
    delta: str
    type: str = EventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA


@dataclass
class ResponseAudioTranscriptDone(ServerToClientMessage):
    response_id: str
    output_index: int
    content_index: int
    transcript: str
    type: str = EventType.RESPONSE_AUDIO_TRANSCRIPT_DONE


@dataclass
class ResponseAudioDelta(ServerToClientMessage):
    output_index: int
    content_index: int
    delta: str
    type: str = EventType.RESPONSE_AUDIO_DELTA


@dataclass
class ResponseAudioDone(ServerToClientMessage):
    output_index: int
    content_index: int
    type: str = EventType.RESPONSE_AUDIO_DONE


@dataclass
class ResponseFunctionCallArgumentsDelta(ServerToClientMessage):
    output_index: int
    call_id: str
    delta: str
    type: str = EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA


@dataclass
class ResponseFunctionCallArgumentsDone(ServerToClientMessage):
    output_index: int
    # call_id: str
    name: str
    arguments: str
    type: str = EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE


@dataclass
class RateLimitDetails:
    name: str  # Name of the rate limit, e.g., "api_requests", "message_generation"
    limit: int  # The maximum number of allowed requests in the current time window
    remaining: int  # The number of requests remaining in the current time window
    reset_seconds: float  # The number of seconds until the rate limit resets


@dataclass
class RateLimitsUpdated(ServerToClientMessage):
    rate_limits: List[RateLimitDetails]
    type: str = EventType.RATE_LIMITS_UPDATED


@dataclass
class ResponseOutputItemAdded(ServerToClientMessage):
    response_id: str  # The ID of the response
    output_index: int  # Index of the output item in the response
    item: Union[
        ItemParam, None
    ]  # The added item (can be a message, function call, etc.)
    type: str = EventType.RESPONSE_OUTPUT_ITEM_ADDED  # Fixed event type


@dataclass
class ResponseContentPartAdded(ServerToClientMessage):
    response_id: str  # The ID of the response
    item_id: str  # The ID of the item to which the content part was added
    output_index: int  # Index of the output item in the response
    content_index: int  # Index of the content part in the output
    part: Union[ItemParam, None]  # The added content part
    content: Union[ItemParam, None] = None  # The added content part for azure
    type: str = EventType.RESPONSE_CONTENT_PART_ADDED  # Fixed event type


@dataclass
class ResponseContentPartDone(ServerToClientMessage):
    response_id: str  # The ID of the response
    item_id: str  # The ID of the item to which the content part belongs
    output_index: int  # Index of the output item in the response
    content_index: int  # Index of the content part in the output
    part: Union[ItemParam, None]  # The content part that was completed
    content: Union[ItemParam, None] = None  # The added content part for azure
    type: str = EventType.RESPONSE_CONTENT_PART_ADDED  # Fixed event type


@dataclass
class ResponseOutputItemDone(ServerToClientMessage):
    response_id: str  # The ID of the response
    output_index: int  # Index of the output item in the response
    item: Union[ItemParam, None]  # The output item that was completed
    type: str = EventType.RESPONSE_OUTPUT_ITEM_DONE  # Fixed event type


@dataclass
class ItemInputAudioTranscriptionCompleted(ServerToClientMessage):
    content_index: int  # Index of the content part that was transcribed
    transcript: str  # The transcribed text
    type: str = EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED  # Fixed event type


@dataclass
class ItemInputAudioTranscriptionFailed(ServerToClientMessage):
    content_index: int  # Index of the content part that failed to transcribe
    error: ResponseError  # Error details explaining the failure
    type: str = EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED  # Fixed event type


# Union of all server-to-client message types
ServerToClientMessages = Union[
    ErrorMessage,
    SessionCreated,
    SessionUpdated,
    InputAudioBufferCommitted,
    InputAudioBufferCleared,
    InputAudioBufferSpeechStarted,
    InputAudioBufferSpeechStopped,
    ItemCreated,
    ItemTruncated,
    ItemDeleted,
    ResponseCreated,
    ResponseDone,
    ResponseTextDelta,
    ResponseTextDone,
    ResponseAudioTranscriptDelta,
    ResponseAudioTranscriptDone,
    ResponseAudioDelta,
    ResponseAudioDone,
    ResponseFunctionCallArgumentsDelta,
    ResponseFunctionCallArgumentsDone,
    RateLimitsUpdated,
    ResponseOutputItemAdded,
    ResponseContentPartAdded,
    ResponseContentPartDone,
    ResponseOutputItemDone,
    ItemInputAudioTranscriptionCompleted,
    ItemInputAudioTranscriptionFailed,
]


# Base class for all ClientToServerMessages
@dataclass
class ClientToServerMessage:
    event_id: str = field(default_factory=generate_event_id)


@dataclass
class InputAudioBufferAppend(ClientToServerMessage):
    audio: Optional[str] = field(default=None)
    type: str = (
        EventType.INPUT_AUDIO_BUFFER_APPEND
    )  # Default argument (has a default value)


@dataclass
class InputAudioBufferCommit(ClientToServerMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_COMMIT


@dataclass
class InputAudioBufferClear(ClientToServerMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_CLEAR


@dataclass
class ItemCreate(ClientToServerMessage):
    item: Optional[ItemParam] = field(
        default=None
    )  # Assuming `ItemParam` is already defined
    type: str = EventType.ITEM_CREATE
    previous_item_id: Optional[str] = None


@dataclass
class ItemTruncate(ClientToServerMessage):
    item_id: Optional[str] = field(default=None)
    content_index: Optional[int] = field(default=None)
    audio_end_ms: Optional[int] = field(default=None)
    type: str = EventType.ITEM_TRUNCATE


@dataclass
class ItemDelete(ClientToServerMessage):
    item_id: Optional[str] = field(default=None)
    type: str = EventType.ITEM_DELETE


@dataclass
class ResponseCreateParams:
    commit: bool = (
        True  # Whether the generated messages should be appended to the conversation
    )
    cancel_previous: bool = True  # Whether to cancel the previous pending generation
    append_input_items: Optional[List[ItemParam]] = (
        None  # Messages to append before response generation
    )
    input_items: Optional[List[ItemParam]] = (
        None  # Initial messages to use for generation
    )
    modalities: Optional[Set[str]] = None  # Allowed modalities (e.g., "text", "audio")
    instructions: Optional[str] = None  # Instructions or guidance for the model
    # voice: Optional[Voices] = None  # Voice setting for audio output
    output_audio_format: Optional[AudioFormats] = None  # Format for the audio output
    tools: Optional[List[Dict[str, Any]]] = None  # Tools available for this response
    tool_choice: Optional[ToolChoice] = (
        None  # How to choose the tool ("auto", "required", etc.)
    )
    temperature: Optional[float] = None  # The randomness of the model's responses
    max_response_output_tokens: Optional[Union[int, str]] = (
        None  # Max number of tokens for the output, "inf" for infinite
    )


@dataclass
class ResponseCreate(ClientToServerMessage):
    type: str = EventType.RESPONSE_CREATE
    response: Optional[ResponseCreateParams] = (
        None  # Assuming `ResponseCreateParams` is defined
    )


@dataclass
class ResponseCancel(ClientToServerMessage):
    type: str = EventType.RESPONSE_CANCEL


DEFAULT_CONVERSATION = "default"


@dataclass
class UpdateConversationConfig(ClientToServerMessage):
    type: str = EventType.UPDATE_CONVERSATION_CONFIG
    label: str = DEFAULT_CONVERSATION
    subscribe_to_user_audio: Optional[bool] = None
    # voice: Optional[Voices] = None
    system_message: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[dict]] = None
    tool_choice: Optional[ToolChoice] = None
    disable_audio: Optional[bool] = None
    output_audio_format: Optional[AudioFormats] = None


@dataclass
class SessionUpdate(ClientToServerMessage):
    session: Optional[SessionUpdateParams] = field(
        default=None
    )  # Assuming `SessionUpdateParams` is defined
    type: str = EventType.SESSION_UPDATE


# Union of all client-to-server message types
ClientToServerMessages = Union[
    InputAudioBufferAppend,
    InputAudioBufferCommit,
    InputAudioBufferClear,
    ItemCreate,
    ItemTruncate,
    ItemDelete,
    ResponseCreate,
    ResponseCancel,
    UpdateConversationConfig,
    SessionUpdate,
]


def from_dict(data_class, data):
    """Recursively convert a dictionary to a dataclass instance."""
    if is_dataclass(data_class):  # Check if the target class is a dataclass
        fieldtypes = {f.name: f.type for f in data_class.__dataclass_fields__.values()}
        # Filter out keys that are not in the dataclass fields
        valid_data = {f: data[f] for f in fieldtypes if f in data}
        return data_class(
            **{f: from_dict(fieldtypes[f], valid_data[f]) for f in valid_data}
        )
    elif isinstance(data, list):  # Handle lists of nested dataclass objects
        return [from_dict(data_class.__args__[0], item) for item in data]
    else:  # For primitive types (str, int, float, etc.), return the value as-is
        return data


def parse_client_message(unparsed_string: str) -> ClientToServerMessage:
    data = json.loads(unparsed_string)

    # Dynamically select the correct message class based on the `type` field, using from_dict
    if data["type"] == EventType.INPUT_AUDIO_BUFFER_APPEND:
        return from_dict(InputAudioBufferAppend, data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_COMMIT:
        return from_dict(InputAudioBufferCommit, data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_CLEAR:
        return from_dict(InputAudioBufferClear, data)
    elif data["type"] == EventType.ITEM_CREATE:
        return from_dict(ItemCreate, data)
    elif data["type"] == EventType.ITEM_TRUNCATE:
        return from_dict(ItemTruncate, data)
    elif data["type"] == EventType.ITEM_DELETE:
        return from_dict(ItemDelete, data)
    elif data["type"] == EventType.RESPONSE_CREATE:
        return from_dict(ResponseCreate, data)
    elif data["type"] == EventType.RESPONSE_CANCEL:
        return from_dict(ResponseCancel, data)
    elif data["type"] == EventType.UPDATE_CONVERSATION_CONFIG:
        return from_dict(UpdateConversationConfig, data)
    elif data["type"] == EventType.SESSION_UPDATE:
        return from_dict(SessionUpdate, data)

    raise ValueError(f"Unknown message type: {data['type']}")


# Assuming all necessary classes and enums (EventType, ServerToClientMessages, etc.) are imported
# Here’s how you can dynamically parse a server-to-client message based on the `type` field:


def parse_server_message(unparsed_string: str) -> ServerToClientMessage:
    data = json.loads(unparsed_string)

    # Dynamically select the correct message class based on the `type` field, using from_dict
    if data["type"] == EventType.ERROR:
        return from_dict(ErrorMessage, data)
    elif data["type"] == EventType.SESSION_CREATED:
        return from_dict(SessionCreated, data)
    elif data["type"] == EventType.SESSION_UPDATED:
        return from_dict(SessionUpdated, data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_COMMITTED:
        return from_dict(InputAudioBufferCommitted, data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_CLEARED:
        return from_dict(InputAudioBufferCleared, data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
        return from_dict(InputAudioBufferSpeechStarted, data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
        return from_dict(InputAudioBufferSpeechStopped, data)
    elif data["type"] == EventType.ITEM_CREATED:
        return from_dict(ItemCreated, data)
    elif data["type"] == EventType.ITEM_TRUNCATED:
        return from_dict(ItemTruncated, data)
    elif data["type"] == EventType.ITEM_DELETED:
        return from_dict(ItemDeleted, data)
    elif data["type"] == EventType.RESPONSE_CREATED:
        return from_dict(ResponseCreated, data)
    elif data["type"] == EventType.RESPONSE_DONE:
        return from_dict(ResponseDone, data)
    elif data["type"] == EventType.RESPONSE_TEXT_DELTA:
        return from_dict(ResponseTextDelta, data)
    elif data["type"] == EventType.RESPONSE_TEXT_DONE:
        return from_dict(ResponseTextDone, data)
    elif data["type"] == EventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
        return from_dict(ResponseAudioTranscriptDelta, data)
    elif data["type"] == EventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
        return from_dict(ResponseAudioTranscriptDone, data)
    elif data["type"] == EventType.RESPONSE_AUDIO_DELTA:
        return from_dict(ResponseAudioDelta, data)
    elif data["type"] == EventType.RESPONSE_AUDIO_DONE:
        return from_dict(ResponseAudioDone, data)
    elif data["type"] == EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA:
        return from_dict(ResponseFunctionCallArgumentsDelta, data)
    elif data["type"] == EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
        return from_dict(ResponseFunctionCallArgumentsDone, data)
    elif data["type"] == EventType.RATE_LIMITS_UPDATED:
        return from_dict(RateLimitsUpdated, data)
    elif data["type"] == EventType.RESPONSE_OUTPUT_ITEM_ADDED:
        return from_dict(ResponseOutputItemAdded, data)
    elif data["type"] == EventType.RESPONSE_CONTENT_PART_ADDED:
        return from_dict(ResponseContentPartAdded, data)
    elif data["type"] == EventType.RESPONSE_CONTENT_PART_DONE:
        return from_dict(ResponseContentPartDone, data)
    elif data["type"] == EventType.RESPONSE_OUTPUT_ITEM_DONE:
        return from_dict(ResponseOutputItemDone, data)
    elif data["type"] == EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
        return from_dict(ItemInputAudioTranscriptionCompleted, data)
    elif data["type"] == EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED:
        return from_dict(ItemInputAudioTranscriptionFailed, data)

    raise ValueError(f"Unknown message type: {data['type']}")


def to_json(obj: Union[ClientToServerMessage, ServerToClientMessage]) -> str:
    # ignore none value
    return json.dumps(
        asdict(obj, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})
    )
