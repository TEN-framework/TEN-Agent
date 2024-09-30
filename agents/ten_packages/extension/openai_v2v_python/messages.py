import abc
from enum import Enum
from typing import Annotated, Any, Literal, Set

from pydantic import BaseModel, PrivateAttr, TypeAdapter
from pydantic.fields import Field
from typing_extensions import override

from .id import generate_event_id, generate_response_id

####################################################################################################
# Common
####################################################################################################


class RealtimeError(BaseModel):
    type: str
    code: str | None = None
    message: str
    param: str | None = None
    event_id: str | None = None


class ApiError(BaseModel):
    type: str
    code: str | None = None
    message: str
    param: str | None = None


class ResponseError(BaseModel):
    type: str
    code: str | None = None
    message: str


DEFAULT_CONVERSATION = "default"

DEFAULT_TEMPERATURE = 0.8


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


DEFAULT_VOICE = Voices.Alloy


class AudioFormats(str, Enum):
    PCM16 = "pcm16"
    G711_ULAW = "g711_ulaw"
    G711_ALAW = "g711_alaw"


DEFAULT_AUDIO_FORMAT = AudioFormats.PCM16


class InputAudioTranscription(BaseModel):
    # FIXME: add enabled
    model: Literal["whisper-1"]


class ServerVAD(BaseModel):
    type: Literal["server_vad"] = "server_vad"
    threshold: float | None = None
    prefix_padding_ms: int | None = None
    silence_duration_ms: int | None = None


VAD_THRESHOLD_DEFAULT = 0.5
VAD_PREFIX_PADDING_MS_DEFAULT = 300
VAD_SILENCE_DURATION_MS_DEFAULT = 200
DEFAULT_TURN_DETECTION = ServerVAD(
    threshold=VAD_THRESHOLD_DEFAULT,
    prefix_padding_ms=VAD_PREFIX_PADDING_MS_DEFAULT,
    silence_duration_ms=VAD_SILENCE_DURATION_MS_DEFAULT,
)


class ServerVADUpdateParams(BaseModel):
    # Always required
    type: Literal["server_vad"]
    threshold: float | None = None
    prefix_padding_ms: int | None = None
    silence_duration_ms: int | None = None


class FunctionToolChoice(BaseModel):
    type: Literal["function"] = "function"
    name: str


ToolChoice = Literal["none", "auto", "required"] | FunctionToolChoice


class ItemType(str, Enum):
    message = "message"
    function_call = "function_call"
    function_call_output = "function_call_output"


class MessageRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class ContentType(str, Enum):
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

ItemParamStatus = Literal["incomplete", "completed"]


class SystemMessageItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.message] = ItemType.message
    status: ItemParamStatus | None = None
    role: Literal[MessageRole.system] = MessageRole.system
    content: list[SystemContentPartParam]


class UserMessageItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.message] = ItemType.message
    status: ItemParamStatus | None = None
    role: Literal[MessageRole.user] = MessageRole.user
    content: list[UserContentPartParam]


class AssistantMessageItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.message] = ItemType.message
    status: ItemParamStatus | None = None
    role: Literal[MessageRole.assistant] = MessageRole.assistant
    content: list[AssistantContentPartParam]


class MessageReferenceItemParam(BaseModel):
    type: Literal[ItemType.message] = ItemType.message
    id: str


class FunctionCallItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.function_call] = ItemType.function_call
    status: ItemParamStatus | None = None
    name: str
    call_id: str
    arguments: str


class FunctionCallOutputItemParam(BaseModel):
    id: str | None = None
    type: Literal[ItemType.function_call_output] = ItemType.function_call_output
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
    status: ItemStatus
    role: MessageRole
    content: list[ContentPart]


class FunctionCallItem(BaseItem):
    type: Literal[ItemType.function_call] = ItemType.function_call
    status: ItemStatus
    name: str
    call_id: str
    arguments: str


class FunctionCallOutputItem(BaseItem):
    type: Literal[ItemType.function_call_output] = ItemType.function_call_output
    call_id: str
    output: str


Item = MessageItem | FunctionCallItem | FunctionCallOutputItem
OutputItem = MessageItem | FunctionCallItem

ResponseStatus = Literal["in_progress", "completed", "cancelled", "incomplete", "failed"]


class ResponseCancelledDetails(BaseModel):
    type: Literal["cancelled"] = "cancelled"
    reason: Literal["turn_detected", "client_cancelled"]


class ResponseIncompleteDetails(BaseModel):
    type: Literal["incomplete"] = "incomplete"
    reason: Literal["max_output_tokens", "content_filter"]


class ResponseFailedDetails(BaseModel):
    type: Literal["failed"] = "failed"
    error: ResponseError


ResponseStatusDetails = ResponseCancelledDetails | ResponseIncompleteDetails | ResponseFailedDetails


class InputTokenDetails(BaseModel):
    cached_tokens: int = 0
    text_tokens: int = 0
    audio_tokens: int = 0


class OutputTokenDetails(BaseModel):
    text_tokens: int = 0
    audio_tokens: int = 0


class Usage(BaseModel):
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    input_token_details: InputTokenDetails = InputTokenDetails()
    output_token_details: OutputTokenDetails = OutputTokenDetails()


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
    """
    Update Events in the OpenAI API have specific behavior:
    - If a field is not provided, it is not updated.
    - If a field is provided, the new value is used for the field.
        - If a null value is provided for a nullable field, that field is updated to null.
        - If a null value is provided for a non-nullable field, the API will return an invalid type error.
    - If a nested field is provided, and the parent object's type matches the current parent's type,
      only that field is updated (i.e. the API supports sparse updates). If the parent object's type
      is different from the current parent's type, the entire object is updated.
    """

    model: str | None = None
    modalities: Set[Literal["text", "audio"]] | None = None
    instructions: str | None = None
    voice: Voices | None = None
    turn_detection: ServerVADUpdateParams | None = None
    input_audio_format: AudioFormats | None = None
    output_audio_format: AudioFormats | None = None
    input_audio_transcription: InputAudioTranscription | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: ToolChoice | None = None
    temperature: float | None = None
    max_response_output_tokens: int | Literal["inf"] | None = None


class SessionUpdate(ClientToServerMessage):
    type: Literal[EventType.SESSION_UPDATE] = EventType.SESSION_UPDATE
    session: SessionUpdateParams

    @override
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """
        Override model_dump to ensure `session` only includes set fields.
        """
        dict_value = super().model_dump(**kwargs)
        dict_value["session"] = self.session.model_dump(**kwargs, exclude_unset=True)
        return dict_value

    @override
    def model_dump_json(self, **kwargs) -> str:
        """
        Override model_dump_json to ensure `session` only includes set fields.
        """
        dict_value = self.model_dump(**kwargs)
        return self.__pydantic_serializer__.to_json(value=dict_value, **kwargs).decode()


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
    # TODO: gate to enabled users
    cancel_previous: bool = True
    # TODO: gate to enabled users
    append_input_items: list[ItemParam] | None = None
    # TODO: gate to enabled users
    input_items: list[ItemParam] | None = None
    modalities: Set[Literal["text", "audio"]] | None = None
    instructions: str | None = None
    voice: Voices | None = None
    output_audio_format: AudioFormats | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: ToolChoice | None = None
    temperature: float | None = None
    max_output_tokens: int | Literal["inf"] | None = None


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


class Session(BaseModel):
    id: str
    object: Literal["realtime.session"] = "realtime.session"
    model: str
    expires_at: int
    """
    The time at which this session will be forceably closed, expressed in seconds since epoch.
    """
    modalities: Set[Literal["text", "audio"]] = Field(default_factory=lambda: {"text", "audio"})
    instructions: str
    voice: Voices = DEFAULT_VOICE
    turn_detection: ServerVAD | None = DEFAULT_TURN_DETECTION  # null indicates disabled
    input_audio_format: AudioFormats = DEFAULT_AUDIO_FORMAT
    output_audio_format: AudioFormats = DEFAULT_AUDIO_FORMAT
    input_audio_transcription: InputAudioTranscription | None = None  # null indicates disabled
    tools: list[dict] = []
    tool_choice: Literal["auto", "none", "required"] = "auto"
    temperature: float = DEFAULT_TEMPERATURE
    max_response_output_tokens: int | Literal["inf"] = "inf"


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
    error: ApiError


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
    item: OutputItem


class ResponseOutputItemDone(ServerToClientMessage):
    type: Literal[EventType.RESPONSE_OUTPUT_ITEM_DONE] = EventType.RESPONSE_OUTPUT_ITEM_DONE
    response_id: str
    output_index: int
    item: OutputItem


class ResponseContentPartAdded(ServerToClientMessage):
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
    | ResponseContentPartAdded
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
