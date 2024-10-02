import json

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Literal, Optional, List, Set, Union
from enum import Enum

# Enums
class Voices(str, Enum):
    Alloy = "alloy"
    Echo = "echo"
    Fable = "fable"
    Nova = "nova"
    Nova_2 = "nova_2"
    Nova_3 = "nova_3"
    Nova_4 = "nova_4"
    Nova_5 = "nova_5"
    Onyx = "onyx"
    Shimmer = "shimmer"

class AudioFormats(str, Enum):
    PCM16 = "pcm16"
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

@dataclass
class FunctionToolChoice:
    type: str = "function"  # Fixed value for type
    name: str  # Name of the function

# ToolChoice can be either a literal string or FunctionToolChoice
ToolChoice = Union[str, FunctionToolChoice]  # "none", "auto", "required", or FunctionToolChoice

@dataclass
class RealtimeError:
    type: str  # The type of the error
    code: Optional[str] = None  # Optional error code
    message: str  # The error message
    param: Optional[str] = None  # Optional parameter related to the error
    event_id: Optional[str] = None  # Optional event ID for tracing

@dataclass
class InputAudioTranscription:
    model: str = "whisper-1"  # Default transcription model is "whisper-1"

@dataclass
class ServerVADUpdateParams:
    type: str = "server_vad"  # Fixed value for VAD type
    threshold: Optional[float] = None  # Threshold for voice activity detection
    prefix_padding_ms: Optional[int] = None  # Amount of padding before the voice starts (in milliseconds)
    silence_duration_ms: Optional[int] = None  # Duration of silence before considering speech stopped (in milliseconds)

@dataclass
class SessionUpdateParams:
    model: Optional[str] = None  # Optional string to specify the model
    modalities: Optional[Set[str]] = None  # Set of allowed modalities (e.g., "text", "audio")
    instructions: Optional[str] = None  # Optional instructions string
    voice: Optional[Voices] = None  # Voice selection, can be `None` or from `Voices` Enum
    turn_detection: Optional[ServerVADUpdateParams] = None  # Server VAD update params
    input_audio_format: Optional[AudioFormats] = None  # Input audio format from `AudioFormats` Enum
    output_audio_format: Optional[AudioFormats] = None  # Output audio format from `AudioFormats` Enum
    input_audio_transcription: Optional[InputAudioTranscription] = None  # Optional transcription model
    tools: Optional[List[Dict[str, Union[str, any]]]] = None  # List of tools (e.g., dictionaries)
    tool_choice: Optional[ToolChoice] = None  # ToolChoice, either string or `FunctionToolChoice`
    temperature: Optional[float] = None  # Optional temperature for response generation
    max_response_output_tokens: Optional[Union[int, str]] = None  # Max response tokens, "inf" for infinite

# Define individual message item param types
@dataclass
class SystemMessageItemParam:
    id: Optional[str] = None
    type: str = "message"
    status: Optional[str] = None
    role: str = "system"
    content: List[dict]  # This can be more specific based on content structure

@dataclass
class UserMessageItemParam:
    id: Optional[str] = None
    type: str = "message"
    status: Optional[str] = None
    role: str = "user"
    content: List[dict]  # Similarly, content can be more specific

@dataclass
class AssistantMessageItemParam:
    id: Optional[str] = None
    type: str = "message"
    status: Optional[str] = None
    role: str = "assistant"
    content: List[dict]  # Content structure here depends on your schema

@dataclass
class FunctionCallItemParam:
    id: Optional[str] = None
    type: str = "function_call"
    status: Optional[str] = None
    name: str
    call_id: str
    arguments: str

@dataclass
class FunctionCallOutputItemParam:
    id: Optional[str] = None
    type: str = "function_call_output"
    call_id: str
    output: str

# Union of all possible item types
ItemParam = Union[
    SystemMessageItemParam,
    UserMessageItemParam,
    AssistantMessageItemParam,
    FunctionCallItemParam,
    FunctionCallOutputItemParam
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
    ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED = "conversation.item.input_audio_transcription.completed"
    ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED = "conversation.item.input_audio_transcription.failed"

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
    type: str = EventType.ERROR
    error: RealtimeError


@dataclass
class SessionCreated(ServerToClientMessage):
    type: str = EventType.SESSION_CREATED
    session: SessionUpdateParams


@dataclass
class SessionUpdated(ServerToClientMessage):
    type: str = EventType.SESSION_UPDATED
    session: SessionUpdateParams


@dataclass
class InputAudioBufferCommitted(ServerToClientMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_COMMITTED
    previous_item_id: Optional[str] = None
    item_id: str


@dataclass
class InputAudioBufferCleared(ServerToClientMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_CLEARED


@dataclass
class InputAudioBufferSpeechStarted(ServerToClientMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED
    audio_start_ms: int
    item_id: str


@dataclass
class InputAudioBufferSpeechStopped(ServerToClientMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED
    audio_end_ms: int
    item_id: Optional[str] = None


@dataclass
class ItemCreated(ServerToClientMessage):
    type: str = EventType.ITEM_CREATED
    previous_item_id: Optional[str] = None
    item: ItemParam


@dataclass
class ItemTruncated(ServerToClientMessage):
    type: str = EventType.ITEM_TRUNCATED
    item_id: str
    content_index: int
    audio_end_ms: int


@dataclass
class ItemDeleted(ServerToClientMessage):
    type: str = EventType.ITEM_DELETED
    item_id: str


# Assuming the necessary enums, ItemParam, and other classes are defined above
# ResponseStatus could be a string or an enum, depending on your schema

# Enum or Literal for ResponseStatus (could be more extensive)
ResponseStatus = Union[str, Literal["in_progress", "completed", "cancelled", "incomplete", "failed"]]

# Define status detail classes
@dataclass
class ResponseCancelledDetails:
    type: str = "cancelled"
    reason: str  # e.g., "turn_detected", "client_cancelled"

@dataclass
class ResponseIncompleteDetails:
    type: str = "incomplete"
    reason: str  # e.g., "max_output_tokens", "content_filter"

@dataclass
class ResponseError:
    type: str  # The type of the error, e.g., "validation_error", "server_error"
    code: Optional[str] = None  # Optional error code, e.g., HTTP status code, API error code
    message: str  # The error message describing what went wrong

@dataclass
class ResponseFailedDetails:
    type: str = "failed"
    error: ResponseError  # Assuming ResponseError is already defined

# Union of possible status details
ResponseStatusDetails = Union[ResponseCancelledDetails, ResponseIncompleteDetails, ResponseFailedDetails]

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
    object: str = "realtime.response"  # Fixed value for object type
    id: str  # Unique ID for the response
    status: ResponseStatus = "in_progress"  # Status of the response
    status_details: Optional[ResponseStatusDetails] = None  # Additional details based on status
    output: List[ItemParam] = field(default_factory=list)  # List of items in the response
    usage: Optional[Usage] = None  # Token usage information



@dataclass
class ResponseCreated(ServerToClientMessage):
    type: str = EventType.RESPONSE_CREATED
    response: Response


@dataclass
class ResponseDone(ServerToClientMessage):
    type: str = EventType.RESPONSE_DONE
    response: Response


@dataclass
class ResponseTextDelta(ServerToClientMessage):
    type: str = EventType.RESPONSE_TEXT_DELTA
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


@dataclass
class ResponseTextDone(ServerToClientMessage):
    type: str = EventType.RESPONSE_TEXT_DONE
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    text: str


@dataclass
class ResponseAudioTranscriptDelta(ServerToClientMessage):
    type: str = EventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


@dataclass
class ResponseAudioTranscriptDone(ServerToClientMessage):
    type: str = EventType.RESPONSE_AUDIO_TRANSCRIPT_DONE
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    transcript: str


@dataclass
class ResponseAudioDelta(ServerToClientMessage):
    type: str = EventType.RESPONSE_AUDIO_DELTA
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


@dataclass
class ResponseAudioDone(ServerToClientMessage):
    type: str = EventType.RESPONSE_AUDIO_DONE
    response_id: str
    item_id: str
    output_index: int
    content_index: int


@dataclass
class ResponseFunctionCallArgumentsDelta(ServerToClientMessage):
    type: str = EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA
    response_id: str
    item_id: str
    output_index: int
    call_id: str
    delta: str


@dataclass
class ResponseFunctionCallArgumentsDone(ServerToClientMessage):
    type: str = EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE
    response_id: str
    item_id: str
    output_index: int
    call_id: str
    name: str
    arguments: str


@dataclass
class RateLimitDetails:
    name: str  # Name of the rate limit, e.g., "api_requests", "message_generation"
    limit: int  # The maximum number of allowed requests in the current time window
    remaining: int  # The number of requests remaining in the current time window
    reset_seconds: float  # The number of seconds until the rate limit resets

@dataclass
class RateLimitsUpdated(ServerToClientMessage):
    type: str = EventType.RATE_LIMITS_UPDATED
    rate_limits: List[RateLimitDetails]


@dataclass
class ResponseOutputItemAdded(ServerToClientMessage):
    type: str = "response.output_item.added"  # Fixed event type
    response_id: str  # The ID of the response
    output_index: int  # Index of the output item in the response
    item: Union[ItemParam, None]  # The added item (can be a message, function call, etc.)

@dataclass
class ResponseContentPartAdded(ServerToClientMessage):
    type: str = "response.content_part.added"  # Fixed event type
    response_id: str  # The ID of the response
    item_id: str  # The ID of the item to which the content part was added
    output_index: int  # Index of the output item in the response
    content_index: int  # Index of the content part in the output
    part: Union[ItemParam, None]  # The added content part

@dataclass
class ResponseContentPartDone(ServerToClientMessage):
    type: str = "response.content_part.done"  # Fixed event type
    response_id: str  # The ID of the response
    item_id: str  # The ID of the item to which the content part belongs
    output_index: int  # Index of the output item in the response
    content_index: int  # Index of the content part in the output
    part: Union[ItemParam, None]  # The content part that was completed

@dataclass
class ResponseOutputItemDone(ServerToClientMessage):
    type: str = "response.output_item.done"  # Fixed event type
    response_id: str  # The ID of the response
    output_index: int  # Index of the output item in the response
    item: Union[ItemParam, None]  # The output item that was completed

@dataclass
class ItemInputAudioTranscriptionCompleted(ServerToClientMessage):
    type: str = "conversation.item.input_audio_transcription.completed"  # Fixed event type
    item_id: str  # The ID of the item for which transcription was completed
    content_index: int  # Index of the content part that was transcribed
    transcript: str  # The transcribed text

@dataclass
class ItemInputAudioTranscriptionFailed(ServerToClientMessage):
    type: str = "conversation.item.input_audio_transcription.failed"  # Fixed event type
    item_id: str  # The ID of the item for which transcription failed
    content_index: int  # Index of the content part that failed to transcribe
    error: ResponseError  # Error details explaining the failure

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
    ItemInputAudioTranscriptionFailed
]



# Base class for all ClientToServerMessages
@dataclass
class ClientToServerMessage:
    event_id: Optional[str] = None  # Optional since some messages may not need it


@dataclass
class InputAudioBufferAppend(ClientToServerMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_APPEND
    audio: str


@dataclass
class InputAudioBufferCommit(ClientToServerMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_COMMIT


@dataclass
class InputAudioBufferClear(ClientToServerMessage):
    type: str = EventType.INPUT_AUDIO_BUFFER_CLEAR


@dataclass
class ItemCreate(ClientToServerMessage):
    type: str = EventType.ITEM_CREATE
    previous_item_id: Optional[str] = None
    item: ItemParam  # Assuming `ItemParam` is already defined


@dataclass
class ItemTruncate(ClientToServerMessage):
    type: str = EventType.ITEM_TRUNCATE
    item_id: str
    content_index: int
    audio_end_ms: int


@dataclass
class ItemDelete(ClientToServerMessage):
    type: str = EventType.ITEM_DELETE
    item_id: str
    
@dataclass
class ResponseCreateParams:
    commit: bool = True  # Whether the generated messages should be appended to the conversation
    cancel_previous: bool = True  # Whether to cancel the previous pending generation
    append_input_items: Optional[List[ItemParam]] = None  # Messages to append before response generation
    input_items: Optional[List[ItemParam]] = None  # Initial messages to use for generation
    modalities: Optional[Set[str]] = None  # Allowed modalities (e.g., "text", "audio")
    instructions: Optional[str] = None  # Instructions or guidance for the model
    voice: Optional[Voices] = None  # Voice setting for audio output
    output_audio_format: Optional[AudioFormats] = None  # Format for the audio output
    tools: Optional[List[Dict[str, Any]]] = None  # Tools available for this response
    tool_choice: Optional[ToolChoice] = None  # How to choose the tool ("auto", "required", etc.)
    temperature: Optional[float] = None  # The randomness of the model's responses
    max_response_output_tokens: Optional[Union[int, str]] = None  # Max number of tokens for the output, "inf" for infinite


@dataclass
class ResponseCreate(ClientToServerMessage):
    type: str = EventType.RESPONSE_CREATE
    response: Optional[ResponseCreateParams] = None  # Assuming `ResponseCreateParams` is defined


@dataclass
class ResponseCancel(ClientToServerMessage):
    type: str = EventType.RESPONSE_CANCEL

DEFAULT_CONVERSATION = "default"

@dataclass
class UpdateConversationConfig(ClientToServerMessage):
    type: str = EventType.UPDATE_CONVERSATION_CONFIG
    label: str = DEFAULT_CONVERSATION
    subscribe_to_user_audio: Optional[bool] = None
    voice: Optional[Voices] = None
    system_message: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[dict]] = None
    tool_choice: Optional[ToolChoice] = None
    disable_audio: Optional[bool] = None
    output_audio_format: Optional[AudioFormats] = None


@dataclass
class SessionUpdate(ClientToServerMessage):
    type: str = EventType.SESSION_UPDATE
    session: SessionUpdateParams  # Assuming `SessionUpdateParams` is defined


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
    SessionUpdate
]


def parse_client_message(unparsed_string: str) -> ClientToServerMessage:
    data = json.loads(unparsed_string)
    
    if data["type"] == EventType.INPUT_AUDIO_BUFFER_APPEND:
        return InputAudioBufferAppend(**data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_COMMIT:
        return InputAudioBufferCommit(**data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_CLEAR:
        return InputAudioBufferClear(**data)
    elif data["type"] == EventType.ITEM_CREATE:
        return ItemCreate(**data)
    elif data["type"] == EventType.ITEM_TRUNCATE:
        return ItemTruncate(**data)
    elif data["type"] == EventType.ITEM_DELETE:
        return ItemDelete(**data)
    elif data["type"] == EventType.RESPONSE_CREATE:
        return ResponseCreate(**data)
    elif data["type"] == EventType.RESPONSE_CANCEL:
        return ResponseCancel(**data)
    elif data["type"] == EventType.UPDATE_CONVERSATION_CONFIG:
        return UpdateConversationConfig(**data)
    elif data["type"] == EventType.SESSION_UPDATE:
        return SessionUpdate(**data)
    
    raise ValueError(f"Unknown message type: {data['type']}")


# Assuming all necessary classes and enums (EventType, ServerToClientMessages, etc.) are imported
# Here’s how you can dynamically parse a server-to-client message based on the `type` field:

def parse_server_message(unparsed_string: str) -> ServerToClientMessage:
    data = json.loads(unparsed_string)

    # Dynamically select the correct message class based on the `type` field
    if data["type"] == EventType.ERROR:
        return ErrorMessage(**data)
    elif data["type"] == EventType.SESSION_CREATED:
        return SessionCreated(**data)
    elif data["type"] == EventType.SESSION_UPDATED:
        return SessionUpdated(**data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_COMMITTED:
        return InputAudioBufferCommitted(**data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_CLEARED:
        return InputAudioBufferCleared(**data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
        return InputAudioBufferSpeechStarted(**data)
    elif data["type"] == EventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
        return InputAudioBufferSpeechStopped(**data)
    elif data["type"] == EventType.ITEM_CREATED:
        return ItemCreated(**data)
    elif data["type"] == EventType.ITEM_TRUNCATED:
        return ItemTruncated(**data)
    elif data["type"] == EventType.ITEM_DELETED:
        return ItemDeleted(**data)
    elif data["type"] == EventType.RESPONSE_CREATED:
        return ResponseCreated(**data)
    elif data["type"] == EventType.RESPONSE_DONE:
        return ResponseDone(**data)
    elif data["type"] == EventType.RESPONSE_TEXT_DELTA:
        return ResponseTextDelta(**data)
    elif data["type"] == EventType.RESPONSE_TEXT_DONE:
        return ResponseTextDone(**data)
    elif data["type"] == EventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
        return ResponseAudioTranscriptDelta(**data)
    elif data["type"] == EventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
        return ResponseAudioTranscriptDone(**data)
    elif data["type"] == EventType.RESPONSE_AUDIO_DELTA:
        return ResponseAudioDelta(**data)
    elif data["type"] == EventType.RESPONSE_AUDIO_DONE:
        return ResponseAudioDone(**data)
    elif data["type"] == EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA:
        return ResponseFunctionCallArgumentsDelta(**data)
    elif data["type"] == EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
        return ResponseFunctionCallArgumentsDone(**data)
    elif data["type"] == EventType.RATE_LIMITS_UPDATED:
        return RateLimitsUpdated(**data)

    raise ValueError(f"Unknown message type: {data['type']}")
    
def to_json(obj: Union[ClientToServerMessage, ServerToClientMessage]) -> str:
    return json.dumps(asdict(obj))