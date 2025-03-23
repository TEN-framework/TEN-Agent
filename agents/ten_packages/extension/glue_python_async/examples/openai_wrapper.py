import os
import openai
import json
from openai import AsyncOpenAI
import traceback
import logging
import logging.config

from typing import List, Union, Dict, Optional
from pydantic import BaseModel, HttpUrl, ValidationError

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import Depends, FastAPI, HTTPException, Request
import asyncio

# Set up logging
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "file": {
                "level": "DEBUG",
                "formatter": "default",
                "class": "logging.FileHandler",
                "filename": "example.log",
            },
        },
        "loggers": {
            "": {
                "handlers": ["file"],
                "level": "DEBUG",
                "propagate": True,
            },
        },
    }
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Chat Completion API",
    description="API for streaming chat completions with support for text, image, and audio content",
    version="1.0.0",
)

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")


class TextContent(BaseModel):
    type: str = "text"
    text: str


class ImageContent(BaseModel):
    type: str = "image"
    image_url: HttpUrl


class AudioContent(BaseModel):
    type: str = "input_audio"
    input_audio: Dict[str, str]


class ToolFunction(BaseModel):
    name: str
    description: Optional[str]
    parameters: Optional[Dict]
    strict: bool = False


class Tool(BaseModel):
    type: str = "function"
    function: ToolFunction


class ToolChoice(BaseModel):
    type: str = "function"
    function: Optional[Dict]


class ResponseFormat(BaseModel):
    type: str = "json_schema"
    json_schema: Optional[Dict[str, str]]


class SystemMessage(BaseModel):
    role: str = "system"
    content: Union[str, List[str]]


class UserMessage(BaseModel):
    role: str = "user"
    content: Union[str, List[Union[TextContent, ImageContent, AudioContent]]]


class AssistantMessage(BaseModel):
    role: str = "assistant"
    content: Union[str, List[TextContent]] = None
    audio: Optional[Dict[str, str]] = None
    tool_calls: Optional[List[Dict]] = None


class ToolMessage(BaseModel):
    role: str = "tool"
    content: Union[str, List[str]]
    tool_call_id: str


class ChatCompletionRequest(BaseModel):
    context: Optional[Dict] = None
    model: Optional[str] = None
    messages: List[Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]]
    response_format: Optional[ResponseFormat] = None
    modalities: List[str] = ["text"]
    audio: Optional[Dict[str, str]] = None
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Union[str, ToolChoice]] = "auto"
    parallel_tool_calls: bool = True
    stream: bool = True
    stream_options: Optional[Dict] = None


"""
{'messages': [{'role': 'user', 'content': 'Hello. Hello. Hello.'}, {'role': 'user', 'content': 'Unprocessedable.'}], 'tools': [], 'tools_choice': 'none', 'model': 'gpt-3.5-turbo', 'stream': True}
"""

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token != os.getenv("API_TOKEN"):
        logger.warning("Invalid or missing token")
        raise HTTPException(status_code=403, detail="Invalid or missing token")


@app.post("/chat/completions", dependencies=[Depends(verify_token)])
async def create_chat_completion(request: ChatCompletionRequest, req: Request):
    try:
        logger.debug(f"Received request: {request.json()}")
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
            model=request.model,
            messages=request.messages,  # Directly use request messages
            tool_choice=(
                request.tool_choice if request.tools and request.tool_choice else None
            ),
            tools=request.tools if request.tools else None,
            # modalities=request.modalities,
            response_format=request.response_format,
            stream=request.stream,
            stream_options=request.stream_options,
        )

        if request.stream:

            async def generate():
                try:
                    async for chunk in response:
                        logger.info(f"Received chunk: {chunk}")
                        yield f"data: {json.dumps(chunk.to_dict())}\n\n"
                    yield "data: [DONE]\n\n"
                except asyncio.CancelledError:
                    logger.info("Request was cancelled")
                    raise

            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            result = await response
            return result
    except asyncio.CancelledError:
        logger.info("Request was cancelled")
        raise HTTPException(status_code=499, detail="Request was cancelled")
    except Exception as e:
        traceback_str = "".join(traceback.format_tb(e.__traceback__))
        error_message = f"{str(e)}\n{traceback_str}"
        logger.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)


if __name__ == "__main__":
    import uvicorn
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi import Depends
    import traceback

    """
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")

    if http_proxy or https_proxy:
        proxies = {
            "http": http_proxy,
            "https": https_proxy
        }
        openai.proxy = proxies
    """

    uvicorn.run(app, host="0.0.0.0", port=8000)
