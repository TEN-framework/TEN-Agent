import random
import requests
from openai import OpenAI
from typing import List, Dict, Any, Optional
from .log import logger
from pydantic import BaseModel

DEFAULT_GROUP_CHAT_PROMPT = '''
You are an intelligent audio-in, audio-out assistant named {character}. All incoming users' audio is first processed by a Speech-to-Text (STT) module, which converts it into text before it is passed to you as input. All your textual outputs are converted to audio via a Text-to-Speech (TTS) module before being transmitted back to the users. Additionally, all textual content will be displayed as subtitles in a chat window for the users.

You are capable of recognizing conversations among multiple users and responding to their inquiries through realtime communication. When users are conversing with each other, you should not interrupt but return a JSON indicating {"need_response":false}. When users ask you a question or mention your name "{character}" explicitly, you should respond and return a JSON indicating {"need_response":true, "content":"your response"}.

Rules:
1. Messages from users will be prefixed with their user ID in the format "UserX: message".
2. If the message is a question or explicitly mentions your name "{character}", it indicates a question directed at you. You should respond and return {"need_response":true, "content":"your response"}.
3. If the message is not a question and does not mention your name, it indicates a conversation between users, and you should not interrupt but return {"need_response":false}.
4. All responses must be valid JSON strings formatted as plain text, without using code blocks. The response content must be encapsulated within the "content" field of the JSON response, and all double quotes must be properly escaped.

Example conversations:
User1: How's the weather today?
{character}: {"need_response":true, "content":"The weather is sunny today with a temperature around 25 degrees."}
User2: User1, what are your plans for today?
{character}: {"need_response":false}
User3: I'm planning to go for a walk in the park.
{character}: {"need_response":false}
User2: Sounds good, I might join you.
{character}: {"need_response":false}
User1: {character}, can you recommend a nearby park?
{character}: {"need_response":true, "content":"There's a great park nearby called Central Park."}
User1: Hi, can you hear me?
{character}: {"need_response":true, "content":"Yes, I can hear you."}

Now you can start the conversation.

User1: Hi, can you hear me?
{character}:
'''

DEFAULT_1V1_PROMPT = '''
You are an intelligent audio-in, audio-out assistant named {character}. All incoming users' audio is first processed by a Speech-to-Text (STT) module, which converts it into text before it is passed to you as input. All your textual outputs are converted to audio via a Text-to-Speech (TTS) module before being transmitted back to the users. Additionally, all textual content will be displayed as subtitles in a chat window for the users.

You are capable of recognizing when a single user is interacting with you. When the user asks you a question or mentions your name "{character}" explicitly, you should respond and return a JSON indicating {"need_response":true, "content":"your response"}. If the user has not completed their question or description, you should ask for more details and return a JSON indicating {"need_response":true, "content":"your follow-up question"}.

Rules:
1. Messages from users will be prefixed with their user ID in the format "UserX: message".
2. If the message is a question or explicitly mentions your name "{character}", it indicates a question directed at you. You should respond and return {"need_response":true, "content":"your response"}.
3. If the user's message seems incomplete or unclear, ask for more details and return {"need_response":true, "content":"your follow-up question"}.
4. All responses must be valid JSON strings formatted as plain text, without using code blocks. The response content must be encapsulated within the "content" field of the JSON response, and all double quotes must be properly escaped.

Example conversations:
User: How's the weather today?
{character}: {"need_response":true, "content":"The weather is sunny today with a temperature around 25 degrees."}
User: Can you recommend a nearby park?
{character}: {"need_response":true, "content":"There's a great park nearby called Central Park."}
User: I need help with...
{character}: {"need_response":true, "content":"Can you please provide more details about what you need help with?"}
User: {character}, can you hear me?
{character}: {"need_response":true, "content":"Yes, I can hear you."}

Now you can start the conversation.

User: Hi, can you hear me?
{character}:
'''

class OpenAIChatGPTConfig:
    def __init__(self, 
            base_url: str, 
            api_key: str, 
            model: str, 
            prompt: str,
            frequency_penalty: float, 
            presence_penalty: float, 
            top_p: float, 
            temperature: float, 
            max_tokens: int, 
            character: str,
            seed: Optional[int] = None, 
            proxy_url: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.prompt = prompt
        self.frequency_penalty = frequency_penalty
        self.presence_penalty = presence_penalty
        self.top_p = top_p
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.character = character
        self.seed = seed if seed is not None else random.randint(0, 10000)
        self.proxy_url = proxy_url

    @classmethod
    def default_config(cls):
        return cls(
            base_url="https://api.openai.com/v1",
            api_key="",
            model="gpt-4o",  # Adjust this to match the equivalent of `openai.GPT4o` in the Python library
            prompt="",
            frequency_penalty=0.9,
            presence_penalty=0.9,
            top_p=1.0,
            temperature=0.1,
            max_tokens=512,
            character="Astra",
            seed=random.randint(0, 10000),
            proxy_url=""
        )
    

class OpenAIChatGPT:
    client = None
    def __init__(self, config: OpenAIChatGPTConfig):
        self.config = config
        logger.info(f"OpenAIChatGPT initialized with config: {config.api_key}")
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        self.session = requests.Session()
        if config.proxy_url:
            proxies = {
                "http": config.proxy_url,
                "https": config.proxy_url,
            }
            self.session.proxies.update(proxies)
        self.client.session = self.session

    def get_chat_completions_group_stream(self, messages):
        req = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": DEFAULT_GROUP_CHAT_PROMPT.replace("{character}", self.config.character),
                }
            ],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "presence_penalty": self.config.presence_penalty,
            "frequency_penalty": self.config.frequency_penalty,
            "max_tokens": self.config.max_tokens,
            "seed": self.config.seed,
            "stream": True,
            "response_format": { "type": "json_object" },
        }
        if self.config.prompt:
            req["messages"].append( {"role": "user", "content": self.config.prompt})
        
        req["messages"].extend(messages)

        logger.info("before request: {}".format(req))

        try:
            response = self.client.chat.completions.create(**req)
            return response
        except Exception as e:
            raise Exception(f"CreateChatCompletionStream failed, err: {e}")
    
    def get_chat_completions_stream(self, messages):
        req = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": DEFAULT_1V1_PROMPT.replace("{character}", self.config.character),
                }
            ],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "presence_penalty": self.config.presence_penalty,
            "frequency_penalty": self.config.frequency_penalty,
            "max_tokens": self.config.max_tokens,
            "seed": self.config.seed,
            "stream": True,
            "response_format": { "type": "json_object" },
        }
        if self.config.prompt:
            req["messages"].append( {"role": "user", "content": self.config.prompt})
        
        req["messages"].extend(messages)

        logger.info("before request: {}".format(req))

        try:
            response = self.client.chat.completions.create(**req)
            return response
        except Exception as e:
            raise Exception(f"CreateChatCompletionStream failed, err: {e}")