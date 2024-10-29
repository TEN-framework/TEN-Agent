from typing import TypedDict, Union
from pydantic import BaseModel

class LLMToolMetadataParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool

class LLMToolMetadata(BaseModel):
    name: str
    description: str
    parameters: list[LLMToolMetadataParameter]


class LLMCompletionContentItemText(BaseModel):
    text: str

class LLMCompletionContentItemImage(BaseModel):
    image: str

class LLMCompletionContentItemAudio(BaseModel):
    audio: str

LLMCompletionContentItem = Union[
    LLMCompletionContentItemText, 
    LLMCompletionContentItemImage, 
    LLMCompletionContentItemAudio
]

class LLMToolResult(BaseModel):
    items: list[LLMCompletionContentItem]

class LLMCallCompletionArgs(TypedDict, total=False):
    content: list[LLMCompletionContentItem]

class LLMDataCompletionArgs(TypedDict, total=False):
    content: list[LLMCompletionContentItem]
    no_tool: bool = False