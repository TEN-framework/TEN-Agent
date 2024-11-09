import os
import openai
from openai import AsyncOpenAI
import traceback  # Add this import

from typing import List, Union
from pydantic import BaseModel, HttpUrl

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from fastapi import Depends, FastAPI, HTTPException, Request
import asyncio

app = FastAPI(title="Chat Completion API",
              description="API for streaming chat completions with support for text, image, and audio content",
              version="1.0.0")

# Set your OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

class TextContent(BaseModel):
    type: str = "text"
    text: str

class ImageContent(BaseModel):
    type: str = "image"
    image_url: HttpUrl

class AudioContent(BaseModel):
    type: str = "audio"
    audio_url: HttpUrl

class Message(BaseModel):
    role: str
    content: Union[TextContent, ImageContent, AudioContent, List[Union[TextContent, ImageContent, AudioContent]]]

class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: str
    temperature: float = 1.0
    stream: bool = True

def format_openai_messages(messages):
    formatted_messages = []
    for msg in messages:
        if isinstance(msg.content, list):
            content = []
            for item in msg.content:
                if item.type == "text":
                    content.append({"type": "text", "text": item.text})
                elif item.type == "image":
                    content.append({"type": "image_url", "image_url": str(item.image_url)})
                elif item.type == "audio":
                    content.append({"type": "audio_url", "audio_url": str(item.audio_url)})
        else:
            if msg.content.type == "text":
                content = [{"type": "text", "text": msg.content.text}]
            elif msg.content.type == "image":
                content = [{"type": "image_url", "image_url": {"url": str(msg.content.image_url)}}]
            elif msg.content.type == "audio":
                content = [{"type": "audio_url", "audio_url": {"url": str(msg.content.audio_url)}}]
        
        formatted_messages.append({"role": msg.role, "content": content})
    return formatted_messages

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token != os.getenv("API_TOKEN"):
        raise HTTPException(status_code=403, detail="Invalid or missing token")

@app.post("/chat/completions", dependencies=[Depends(verify_token)])
async def create_chat_completion(request: ChatCompletionRequest, req: Request):
    try:
        messages = format_openai_messages(request.messages)
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            stream=request.stream
        )

        async def generate():
            try:
                async for chunk in response:
                    if chunk.choices[0].delta.content is not None:
                        yield f"data: {chunk.choices[0].delta.content}\n\n"
                yield "data: [DONE]\n\n"
            except asyncio.CancelledError:
                print("Request was cancelled")
                raise

        return StreamingResponse(generate(), media_type="text/event-stream")
    except asyncio.CancelledError:
        print("Request was cancelled")
        raise HTTPException(status_code=499, detail="Request was cancelled")
    except Exception as e:
        traceback_str = ''.join(traceback.format_tb(e.__traceback__))
        error_message = f"{str(e)}\n{traceback_str}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)

if __name__ == "__main__":
    import uvicorn
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi import Depends
    import traceback

    '''
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")

    if http_proxy or https_proxy:
        proxies = {
            "http": http_proxy,
            "https": https_proxy
        }
        openai.proxy = proxies
    '''

    uvicorn.run(app, host="0.0.0.0", port=8000)
