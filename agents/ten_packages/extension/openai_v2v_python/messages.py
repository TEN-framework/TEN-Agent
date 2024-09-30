import abc
import random
import string
from enum import Enum, StrEnum
from typing import Annotated, Any, Literal, Set

from pydantic import BaseModel, PrivateAttr, TypeAdapter
from pydantic.fields import Field

####################################################################################################
# ID Generation
####################################################################################################
# Do not use internal libraries for now.


def generate_rand_str(prefix: str, len: int = 16) -> str:
    # Generate a random string of specified length with the given prefix
    random_str = "".join(random.choices(string.ascii_letters + string.digits, k=len))
    return f"{prefix}_{random_str}"


def generate_event_id() -> str:
    return generate_rand_str("event")


def generate_response_id() -> str:
    return generate_rand_str("resp")


####################################################################################################
# Common
####################################################################################################

DEFAULT_CONVERSATION = "default"

DEFAULT_TEMPERATURE = 0.8


class Voices(str, Enum):
    Alloy = "alloy"
    Echo = "echo"
    Shimmer = "shimmer"


DEFAULT_VOICE = Voices.Alloy


class AudioFormats(str, Enum):
    PCM16 = "pcm16"
    G711_ULAW = "g711_ulaw"
    G711_ALAW = "g711_alaw"


DEFAULT_AUDIO_FORMAT = AudioFormats.PCM16


class InputAudioTranscription(BaseModel):
    # FIXME: add enabled
    model: Literal["whisper-1"]


class NoTurnDetection(BaseModel):
    type: Literal["none"] = "none"


class ServerVAD(BaseModel):
    type: Literal["server_vad"] = "server_vad"
    threshold: float | None = None
    prefix_padding_ms: int | None = None
    silence_duration_ms: int | None = None


TurnDetection = ServerVAD | NoTurnDetection

VAD_THRESHOLD_DEFAULT = 0.5
VAD_PREFIX_PADDING_MS_DEFAULT = 300
VAD_SILENCE_DURATION_MS_DEFAULT = 200
DEFAULT_TURN_DETECTION = ServerVAD(
    threshold=VAD_THRESHOLD_DEFAULT,
    prefix_padding_ms=VAD_PREFIX_PADDING_MS_DEFAULT,
    silence_duration_ms=VAD_SILENCE_DURATION_MS_DEFAULT,
)


class FunctionToolChoice(BaseModel):
    type: Literal["function"] = "function"
    name: str


ToolChoice = Literal["none", "auto", "required"] | FunctionToolChoice


class ItemType(StrEnum):
    message = "message"
    function_call = "function_call"
    function_call_output = "function_call_output"


class MessageRole(StrEnum):
    system = "system"
    user = "user"
    assistant = "assistant"


class ContentType(StrEnum):
    input_text = "input_text"
    input_audio = "input_audio"
    text = "text"
    audio = "audio"


class InputTextContentPartParam(BaseModel):
    type: Literal[ContentType.input_text] = ContentType.input_text
    text: str


class InputAudioContentPartParam(BaseModel):
    type: Literal[ContentType.input_audio] = ContentType.input_audio
    audio: str
    transcript: str | None = None


class OutputTextContentPartParam(BaseModel):
    type: Literal[ContentType.text] = ContentType.text
    text: str


SystemContentPartParam = InputTextContentPartParam
UserContentPartParam = InputTextContentPartParam | InputAudioContentPartParam
AssistantContentPartParam = OutputTextContentPartParam

ItemParamStatus = str
"""
The client can only pass items with status `completed` or `incomplete`,
but we're lenient here since actual validation happens further down.
"""


class SystemMessageItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.message] = ItemType.message
    role: Literal[MessageRole.system] = MessageRole.system
    content: list[SystemContentPartParam]
    status: ItemParamStatus | None = None


class UserMessageItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.message] = ItemType.message
    role: Literal[MessageRole.user] = MessageRole.user
    content: list[UserContentPartParam]
    status: ItemParamStatus | None = None


class AssistantMessageItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.message] = ItemType.message
    role: Literal[MessageRole.assistant] = MessageRole.assistant
    content: list[AssistantContentPartParam]
    status: ItemParamStatus | None = None


class MessageReferenceItemParam(BaseModel):
    type: Literal[ItemType.message] = ItemType.message
    id: str
    status: ItemParamStatus | None = None


class FunctionCallItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.function_call] = ItemType.function_call
    name: str
    call_id: str
    arguments: str
    status: ItemParamStatus | None = None


class FunctionCallOutputItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.function_call_output] = ItemType.function_call_output
    status: ItemParamStatus | None = None
    call_id: str
    output: str


ItemParam = (
    SystemMessageItemParam
    | UserMessageItemParam
    | AssistantMessageItemParam
    | FunctionCallItemParam
    | FunctionCallOutputItemParam
    # Note: it's important this comes after the other item types, so that we accept user-provided
    # item IDs.
    | MessageReferenceItemParam
)

ItemStatus = Literal["in_progress", "completed", "incomplete"]


class BaseItem(BaseModel):
    id: str | None = None
    object: Literal["realtime.item"] | None = None
    type: ItemType
    status: ItemStatus


class InputTextContentPart(BaseModel):
    type: Literal[ContentType.input_text] = ContentType.input_text
    text: str


class InputAudioContentPart(BaseModel):
    type: Literal[ContentType.input_audio] = ContentType.input_audio
    transcript: str | None


class TextContentPart(BaseModel):
    type: Literal[ContentType.text] = ContentType.text
    text: str


class AudioContentPart(BaseModel):
    type: Literal[ContentType.audio] = ContentType.audio
    transcript: str | None
    _audio: str = PrivateAttr(default_factory=str)


ContentPart = InputTextContentPart | InputAudioContentPart | TextContentPart | AudioContentPart


class MessageItem(BaseItem):
    type: Literal[ItemType.message] = ItemType.message
    role: MessageRole
    content: list[ContentPart]


class FunctionCallItem(BaseItem):
    type: Literal[ItemType.function_call] = ItemType.function_call
    name: str
    call_id: str
    arguments: str


class FunctionCallOutputItem(BaseItem):
    type: Literal[ItemType.function_call_output] = ItemType.function_call_output
    call_id: str
    output: str


Item = MessageItem | FunctionCallItem | FunctionCallOutputItem

ResponseStatus = Literal["in_progress", "completed", "cancelled", "incomplete", "failed"]


class ResponseCancelledDetails(BaseModel):
    type: Literal["cancelled"] = "cancelled"
    reason: Literal["turn_detected", "client_cancelled"]


class ResponseIncompleteDetails(BaseModel):
    type: Literal["incomplete"] = "incomplete"
    reason: Literal["max_output_tokens", "content_filter"]


class ResponseFailedDetails(BaseModel):
    type: Literal["failed"] = "failed"
    error: Any


ResponseStatusDetails = ResponseCancelledDetails | ResponseIncompleteDetails | ResponseFailedDetails


class Usage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int


class RateLimitDetails(BaseModel):
    name: str
    limit: int
    remaining: int
    reset_seconds: float


####################################################################################################
# Events
####################################################################################################


class EventType(str, Enum):
    # Client Events

    SESSION_UPDATE = "session.update"
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    INPUT_AUDIO_BUFFER_COMMIT = "input_audio_buffer.commit"
    INPUT_AUDIO_BUFFER_CLEAR = "input_audio_buffer.clear"
    # TODO: gate to enabled users
    UPDATE_CONVERSATION_CONFIG = "update_conversation_config"
    ITEM_CREATE = "conversation.item.create"
    ITEM_TRUNCATE = "conversation.item.truncate"
    ITEM_DELETE = "conversation.item.delete"
    RESPONSE_CREATE = "response.create"
    RESPONSE_CANCEL = "response.cancel"

    # Server Events

    ERROR = "error"
    SESSION_CREATED = "session.created"

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


class RealtimeMessage(BaseModel, abc.ABC):
    type: EventType


####################################################################################################
# Client Events
#
# NOTE: See `api/params/client_events.py` for the xapi source of truth.
#       Keep these classes in sync with the xapi versions for easier client and testing usage.
####################################################################################################
class ClientToServerMessage(RealtimeMessage, abc.ABC):
    event_id: str | None = None


class SessionUpdateParams(BaseModel):
    model: str | None = None
    modalities: Set[Literal["text", "audio"]] | None = None
    voice: Voices | None = None
    instructions: str | None = None
    input_audio_format: AudioFormats | None = None
    output_audio_format: AudioFormats | None = None
    input_audio_transcription: InputAudioTranscription | None = None
    turn_detection: TurnDetection | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: ToolChoice | None = None
    temperature: float | None = None
    # FIXME: support -1
    # max_response_output_tokens: int | None = None


class SessionUpdate(ClientToServerMessage):
    type: Literal[EventType.SESSION_UPDATE] = EventType.SESSION_UPDATE
    session: SessionUpdateParams


class InputAudioBufferAppend(ClientToServerMessage):
    """
    Append audio data to the user audio buffer, this should be in the format specified by
    input_audio_format in the session config.
    """

    type: Literal[EventType.INPUT_AUDIO_BUFFER_APPEND] = EventType.INPUT_AUDIO_BUFFER_APPEND
    audio: str


class InputAudioBufferCommit(ClientToServerMessage):
    """
    Commit the pending user audio buffer, which creates a user message item with the audio content
    and clears the buffer.
    """

    type: Literal[EventType.INPUT_AUDIO_BUFFER_COMMIT] = EventType.INPUT_AUDIO_BUFFER_COMMIT


class InputAudioBufferClear(ClientToServerMessage):
    """
    Clear the user audio buffer, discarding any pending audio data.
    """

    type: Literal[EventType.INPUT_AUDIO_BUFFER_CLEAR] = EventType.INPUT_AUDIO_BUFFER_CLEAR


class ItemCreate(ClientToServerMessage):
    type: Literal[EventType.ITEM_CREATE] = EventType.ITEM_CREATE
    previous_item_id: str | None = None
    item: ItemParam


class ItemTruncate(ClientToServerMessage):
    type: Literal[EventType.ITEM_TRUNCATE] = EventType.ITEM_TRUNCATE
    item_id: str
    content_index: int
    audio_end_ms: int


class ItemDelete(ClientToServerMessage):
    type: Literal[EventType.ITEM_DELETE] = EventType.ITEM_DELETE
    item_id: str


class ResponseCreateParams(BaseModel):
    """
    - commit: If true, the generated messages will be appended to the end of the conversation.
        Only valid if conversation_label is set.
    - cancel_previous: If True, the generation will cancel any pending generation for that specific
        conversation. If False, the generation will be queued and will be generated after the
        previous generation has completed.
    - append_input_items: If set, these messages will be appended to the end of the conversation before
        a response is generated. If commit is false, these messages will be discarded. This can only
        be done with an existing conversation, and thus will throw an error if conversation_label is
        not set or does not exist.
    - input_items: If conversation_label is not set or does not exist, this will be the initial messages
        of the conversation, i.e. the context of the generation. If the conversation exists, this will
        throw an error.
    """

    # TODO: gate to enabled users
    commit: bool = True
    cancel_previous: bool = True
    append_input_items: list[ItemParam] | None = None
    input_items: list[ItemParam] | None = None
    instructions: str | None = None
    modalities: Set[Literal["text", "audio"]] | None = None
    voice: Voices | None = None
    temperature: float | None = None
    # FIXME: support -1
    max_output_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: ToolChoice | None = None
    output_audio_format: AudioFormats | None = None


class ResponseCreate(ClientToServerMessage):
    """
    Trigger model inference to generate a model turn, the response will be streamed back with
    a series of events, starting with an add_message event and ending with a turn_finished event.
    If functions are enabled the response may be two, the second being a tool_call.
    """

    type: Literal[EventType.RESPONSE_CREATE] = EventType.RESPONSE_CREATE
    response: ResponseCreateParams | None = None


class ResponseCancel(ClientToServerMessage):
    type: Literal[EventType.RESPONSE_CANCEL] = EventType.RESPONSE_CANCEL


class Conversation(BaseModel):
    messages: list[Item]
    config: dict[str, Any]


# Temporarily leaving this here to support multi-convo path.
class UpdateConversationConfig(ClientToServerMessage):
    type: Literal[EventType.UPDATE_CONVERSATION_CONFIG] = EventType.UPDATE_CONVERSATION_CONFIG
    label: str = DEFAULT_CONVERSATION
    subscribe_to_user_audio: bool | None = None
    voice: Voices | None = None
    system_message: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: ToolChoice | None = None
    disable_audio: bool | None = None
    output_audio_format: AudioFormats | None = None


####################################################################################################
# Server Events
####################################################################################################


class ServerToClientMessage(RealtimeMessage, abc.ABC):
    event_id: str = Field(default_factory=generate_event_id)


class RealtimeError(BaseModel):
    message: str
    type: str | None = None
    code: str | None = None
    param: str | None = None
    event_id: str | None = None


class Session(BaseModel):
    id: str
    object: Literal["realtime.session"] = "realtime.session"
    model: str
    modalities: Set[Literal["text", "audio"]] = Field(default_factory=lambda: {"text", "audio"})
    instructions: str
    voice: Voices = DEFAULT_VOICE
    input_audio_format: AudioFormats = DEFAULT_AUDIO_FORMAT
    output_audio_format: AudioFormats = DEFAULT_AUDIO_FORMAT
    input_audio_transcription: InputAudioTranscription | None = None
    turn_detection: TurnDetection = DEFAULT_TURN_DETECTION
    tools: list[dict] = []
    tool_choice: Literal["auto", "none", "required"] = "auto"
    temperature: float = DEFAULT_TEMPERATURE
    # FIXME: support -1
    # max_response_output_tokens: int | None = None  # Null indicates infinity


class Response(BaseModel):
    object: Literal["realtime.response"] = "realtime.response"
    id: str = Field(default_factory=generate_response_id)

    status: ResponseStatus = "in_progress"
    status_details: ResponseStatusDetails | None = None

    output: list[Item] = Field(default_factory=list)

    usage: Usage | None = None


class ErrorMessage(ServerToClientMessage):
    type: Literal[EventType.ERROR] = EventType.ERROR
    error: RealtimeError


class SessionCreated(ServerToClientMessage):
    type: Literal[EventType.SESSION_CREATED] = EventType.SESSION_CREATED
    session: Session


class InputAudioBufferCommitted(ServerToClientMessage):
    """
    Signals the server has received and processed the audio buffer.
    """

    type: Literal[EventType.INPUT_AUDIO_BUFFER_COMMITTED] = EventType.INPUT_AUDIO_BUFFER_COMMITTED
    previous_item_id: str | None = None
    # TODO: should we make this match conversation.item.created, and add item instead?
    item_id: str


class InputAudioBufferCleared(ServerToClientMessage):
    """
    Signals the server has cleared the audio buffer.
    """

    type: Literal[EventType.INPUT_AUDIO_BUFFER_CLEARED] = EventType.INPUT_AUDIO_BUFFER_CLEARED


class InputAudioBufferSpeechStarted(ServerToClientMessage):
    """
    If the server VAD is enabled, this event is sent when speech is detected in the user audio buffer.
    It tells you where in the audio stream (in milliseconds) the speech started, plus an item_id
    which will be used in the corresponding speech_stopped event and the item created in the conversation
    when speech stops.
    """

    type: Literal[EventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED] = (
        EventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED
    )
    audio_start_ms: int
    item_id: str


class InputAudioBufferSpeechStopped(ServerToClientMessage):
    """
    If the server VAD is enabled, this event is sent when speech stops in the user audio buffer.
    It tells you where in the audio stream (in milliseconds) the speech stopped, plus an item_id
    which will be used in the corresponding speech_started event and the item created in the conversation
    when speech starts.
    """

    type: Literal[EventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED] = (
        EventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED
    )
    audio_end_ms: int
    item_id: str | None = None


class ItemCreated(ServerToClientMessage):
    type: Literal[EventType.ITEM_CREATED] = EventType.ITEM_CREATED
    previous_item_id: str | None
    item: Item


class ItemTruncated(ServerToClientMessage):
    type: Literal[EventType.ITEM_TRUNCATED] = EventType.ITEM_TRUNCATED
    item_id: str
    content_index: int = 0
    audio_end_ms: int


class ItemDeleted(ServerToClientMessage):
    type: Literal[EventType.ITEM_DELETED] = EventType.ITEM_DELETED
    item_id: str


class ItemInputAudioTranscriptionCompleted(ServerToClientMessage):
    type: Literal[EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED] = (
        EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED
    )
    item_id: str
    content_index: int
    transcript: str


class ItemInputAudioTranscriptionFailed(ServerToClientMessage):
    type: Literal[EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED] = (
        EventType.ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED
    )
    item_id: str
    content_index: int
    error: RealtimeError


class ResponseCreated(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_CREATED] = EventType.RESPONSE_CREATED
    response: Response


class ResponseDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_DONE] = EventType.RESPONSE_DONE
    response: Response


class ResponseOutputItemAdded(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_OUTPUT_ITEM_ADDED] = EventType.RESPONSE_OUTPUT_ITEM_ADDED
    response_id: str
    output_index: int
    item: Item


class ResponseOutputItemDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_OUTPUT_ITEM_DONE] = EventType.RESPONSE_OUTPUT_ITEM_DONE
    response_id: str
    output_index: int
    item: Item


class ResponseContenPartAdded(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_CONTENT_PART_ADDED] = EventType.RESPONSE_CONTENT_PART_ADDED
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    part: ContentPart


class ResponseContentPartDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_CONTENT_PART_DONE] = EventType.RESPONSE_CONTENT_PART_DONE
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    part: ContentPart


class ResponseTextDelta(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_TEXT_DELTA] = EventType.RESPONSE_TEXT_DELTA
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseTextDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_TEXT_DONE] = EventType.RESPONSE_TEXT_DONE
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    text: str


class ResponseAudioTranscriptDelta(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA] = (
        EventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA
    )
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseAudioTranscriptDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_AUDIO_TRANSCRIPT_DONE] = (
        EventType.RESPONSE_AUDIO_TRANSCRIPT_DONE
    )
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    transcript: str


class ResponseAudioDelta(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_AUDIO_DELTA] = EventType.RESPONSE_AUDIO_DELTA
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseAudioDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_AUDIO_DONE] = EventType.RESPONSE_AUDIO_DONE
    response_id: str
    item_id: str
    output_index: int
    content_index: int


class ResponseFunctionCallArgumentsDelta(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA] = (
        EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA
    )
    response_id: str
    item_id: str
    output_index: int
    call_id: str
    delta: str


class ResponseFunctionCallArgumentsDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE] = (
        EventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE
    )
    response_id: str
    item_id: str
    output_index: int
    call_id: str
    name: str
    arguments: str


DeltaType = (
    ResponseTextDelta
    | ResponseAudioDelta
    | ResponseAudioTranscriptDelta
    | ResponseFunctionCallArgumentsDelta
)


class RateLimitsUpdated(ServerToClientMessage):
    type: Literal[EventType.RATE_LIMITS_UPDATED] = EventType.RATE_LIMITS_UPDATED
    rate_limits: list[RateLimitDetails]


ClientToServerMessages = (
    InputAudioBufferAppend
    | InputAudioBufferClear
    | InputAudioBufferCommit
    | ItemCreate
    | ItemDelete
    | ItemTruncate
    | ResponseCancel
    | ResponseCreate
    | SessionUpdate
    # TODO: gate to enabled users
    | UpdateConversationConfig
)


AnnotatedClientToServerMessages = Annotated[ClientToServerMessages, Field(discriminator="type")]


ServerToClientMessages = (
    ErrorMessage
    | InputAudioBufferCleared
    | InputAudioBufferCommitted
    | InputAudioBufferSpeechStarted
    | InputAudioBufferSpeechStopped
    | ItemCreated
    | ItemDeleted
    | ItemInputAudioTranscriptionCompleted
    | ItemTruncated
    | RateLimitsUpdated
    | ResponseAudioDelta
    | ResponseAudioDone
    | ResponseAudioTranscriptDelta
    | ResponseAudioTranscriptDone
    | ResponseContenPartAdded
    | ResponseContentPartDone
    | ResponseCreated
    | ResponseDone
    | ResponseFunctionCallArgumentsDelta
    | ResponseFunctionCallArgumentsDone
    | ResponseOutputItemAdded
    | ResponseOutputItemDone
    | ResponseTextDelta
    | ResponseTextDone
    | SessionCreated
)

AnnotatedServerToClientMessages = Annotated[ServerToClientMessages, Field(discriminator="type")]


def parse_client_message(unparsed_string: str) -> ClientToServerMessage:
    adapter: TypeAdapter[ClientToServerMessages] = TypeAdapter(AnnotatedClientToServerMessages)  # type: ignore[arg-type]
    return adapter.validate_json(unparsed_string)


def parse_server_message(unparsed_string: str) -> ServerToClientMessage:
    adapter: TypeAdapter[ServerToClientMessage] = TypeAdapter(AnnotatedServerToClientMessages)  # type: ignore[arg-type]
    return adapter.validate_json(unparsed_string)
