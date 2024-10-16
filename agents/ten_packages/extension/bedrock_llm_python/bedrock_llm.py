import boto3

from typing import List, Any
from .log import logger

class BedrockLLMConfig:
    def __init__(self, 
            region: str, 
            access_key: str, 
            secret_key: str, 
            model: str, 
            prompt: str, 
            top_p: float, 
            temperature: float,
            max_tokens: int):
        self.region = region
        self.access_key = access_key
        self.secret_key = secret_key
        self.model = model
        self.prompt = prompt
        self.top_p = top_p
        self.temperature = temperature
        self.max_tokens = max_tokens

    @classmethod
    def default_config(cls):
        return cls(
            region="us-east-1",
            access_key="",
            secret_key="",
            model="anthropic.claude-3-5-sonnet-20240620-v1:0", # Defaults to Claude 3.5, supported model list: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
            # system prompt
            prompt="You are a voice assistant who talks in a conversational way and can chat with me like my friends. I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. Don’t talk like a robot, instead I would like you to talk like a real human with emotions. I will use your answer for text-to-speech, so don’t return me any meaningless characters. I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. When giving me a list of options, express the options in a narrative way instead of bullet points.",
            top_p=1.0,
            temperature=0.1,
            max_tokens=512,
        )

class BedrockLLM:
    client = None
    def __init__(self, config: BedrockLLMConfig):
        self.config = config

        if config.access_key and config.secret_key:
            logger.info(f"BedrockLLM initialized with access key: {config.access_key}")

            self.client = boto3.client(service_name='bedrock-runtime', 
                                    region_name=config.region,
                                    aws_access_key_id=config.access_key,
                                    aws_secret_access_key=config.secret_key)
        else:
            logger.info(f"BedrockLLM initialized without access key, using default credentials provider chain.")
            self.client = boto3.client(service_name='bedrock-runtime', region_name=config.region)

    def get_converse_stream(self, messages):
        bedrock_req_params = {
            "modelId": self.config.model,
            "messages": messages,
            "inferenceConfig": {
                "temperature": self.config.temperature,
                "maxTokens": self.config.max_tokens,
                "topP": self.config.top_p,
                # "stopSequences": [],
            },
            # "additionalModelRequestFields": additional_model_fields,
        }

        if self.config.prompt:
            bedrock_req_params['system'] = [
                {'text': self.config.prompt}
            ]

        try:
            response = self.client.converse_stream(**bedrock_req_params)
            return response
        except Exception as e:
            raise Exception(f"GetConverseStream failed, err: {e}")
        
    def chat_completion_cmd(self, messages: List[Any], stream: bool, is_json: bool):
        bedrock_req_params = {
            "modelId": self.config.model,
            "messages": messages,
            "inferenceConfig": {
                "temperature": self.config.temperature,
                "maxTokens": self.config.max_tokens,
                "topP": self.config.top_p,
                # "stopSequences": [],
            },
            # "additionalModelRequestFields": additional_model_fields,
        }

        logger.info(f"before chat {bedrock_req_params}")

        f = self.client.converse_stream
        if not stream:
            f = self.client.converse

        try:
            response = f(**bedrock_req_params)
            logger.info(f"after chat {response}")
            return response
        except Exception as e:
            raise Exception(f"GetConverseStream failed, err: {e}")