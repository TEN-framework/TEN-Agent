from typing import TypedDict, Union
from pydantic import BaseModel

class TenLLMToolMetadataParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool

class TenLLMToolMetadata(BaseModel):
    name: str
    description: str
    parameters: list[TenLLMToolMetadataParameter]


class TenLLMCompletionContentItemText(BaseModel):
    text: str

class TenLLMCompletionContentItemImage(BaseModel):
    image: str

class TenLLMCompletionContentItemAudio(BaseModel):
    audio: str

TenLLMCompletionContentItem = Union[
    TenLLMCompletionContentItemText, 
    TenLLMCompletionContentItemImage, 
    TenLLMCompletionContentItemAudio
]

class TenLLMToolResult(BaseModel):
    items: list[TenLLMCompletionContentItem]

class TenLLMCallCompletionArgs(TypedDict, total=False):
    content: list[TenLLMCompletionContentItem]

class TenLLMDataCompletionArgs(TypedDict, total=False):
    content: list[TenLLMCompletionContentItem]
    no_tool: bool = False