from typing import Literal, Optional, TypedDict, Union
from pydantic import BaseModel

class LLMToolMetadataParameter(BaseModel):
    name: str
    type: str
    description: str
    required: Optional[bool] = False

class LLMToolMetadata(BaseModel):
    name: str
    description: str
    parameters: list[LLMToolMetadataParameter]

class LLMCompletionContentItemJSON(BaseModel):
    json_str: str

class LLMCompletionContentItemText(BaseModel):
    text: str

class LLMCompletionContentItemImage(BaseModel):
    image: str

class LLMCompletionContentItemAudio(BaseModel):
    audio: str

LLMCompletionContentItem = Union[
    LLMCompletionContentItemText, 
    LLMCompletionContentItemImage, 
    LLMCompletionContentItemAudio,
    LLMCompletionContentItemJSON
]



class LLMCompletionArgsMessage(BaseModel):
    role: Literal["system"] | Literal["user"] | Literal["assistant"] | Literal["tool"]
    content: list[LLMCompletionContentItem]
    tool_call_id: Optional[str] = None


class LLMToolResult(BaseModel):
    message: LLMCompletionArgsMessage


class LLMCallCompletionArgs(TypedDict, total=False):
    message: LLMCompletionArgsMessage

class LLMDataCompletionArgs(TypedDict, total=False):
    content: LLMCompletionArgsMessage
    no_tool: bool = False