from typing import Iterable, Optional, TypeAlias, Union
from pydantic import BaseModel
from typing_extensions import Literal, Required, TypedDict

class LLMToolMetadataParameter(BaseModel):
    name: str
    type: str
    description: str
    required: Optional[bool] = False

class LLMToolMetadata(BaseModel):
    name: str
    description: str
    parameters: list[LLMToolMetadataParameter]


class ImageURL(TypedDict, total=False):
    url: Required[str]
    """Either a URL of the image or the base64 encoded image data."""

    detail: Literal["auto", "low", "high"]
    """Specifies the detail level of the image.

    Learn more in the
    [Vision guide](https://platform.openai.com/docs/guides/vision#low-or-high-fidelity-image-understanding).
    """


class LLMChatCompletionContentPartImageParam(TypedDict, total=False):
    image_url: Required[ImageURL]

    type: Required[Literal["image_url"]]
    """The type of the content part."""

class InputAudio(TypedDict, total=False):
    data: Required[str]
    """Base64 encoded audio data."""

    format: Required[Literal["wav", "mp3"]]
    """The format of the encoded audio data. Currently supports "wav" and "mp3"."""


class LLMChatCompletionContentPartInputAudioParam(TypedDict, total=False):
    input_audio: Required[InputAudio]

    type: Required[Literal["input_audio"]]
    """The type of the content part. Always `input_audio`."""

class LLMChatCompletionContentPartTextParam(TypedDict, total=False):
    text: Required[str]
    """The text content."""

    type: Required[Literal["text"]]
    """The type of the content part."""

LLMChatCompletionContentPartParam: TypeAlias = Union[
    LLMChatCompletionContentPartTextParam, LLMChatCompletionContentPartImageParam, LLMChatCompletionContentPartInputAudioParam
]

class LLMChatCompletionToolMessageParam(TypedDict, total=False):
    content: Required[Union[str, Iterable[LLMChatCompletionContentPartTextParam]]]
    """The contents of the tool message."""

    role: Required[Literal["tool"]]
    """The role of the messages author, in this case `tool`."""

    tool_call_id: Required[str]
    """Tool call that this message is responding to."""

class LLMChatCompletionUserMessageParam(TypedDict, total=False):
    content: Required[Union[str, Iterable[LLMChatCompletionContentPartParam]]]
    """The contents of the user message."""

    role: Required[Literal["user"]]
    """The role of the messages author, in this case `user`."""

    name: str
    """An optional name for the participant.

    Provides the model information to differentiate between participants of the same
    role.
    """

LLMChatCompletionMessageParam: TypeAlias = Union[
    LLMChatCompletionUserMessageParam, LLMChatCompletionToolMessageParam
]

class LLMToolResult(TypedDict, total=False):
    content: Required[Union[str, Iterable[LLMChatCompletionContentPartParam]]]

class LLMCallCompletionArgs(TypedDict, total=False):
    messages: Iterable[LLMChatCompletionMessageParam]

class LLMDataCompletionArgs(TypedDict, total=False):
    messages: Iterable[LLMChatCompletionMessageParam]
    no_tool: bool = False


class TTSPcmOptions(TypedDict, total=False):
    sample_rate: int
    """The sample rate of the audio data in Hz."""

    num_channels: int
    """The number of audio channels."""

    bytes_per_sample: int
    """The number of bytes per sample."""