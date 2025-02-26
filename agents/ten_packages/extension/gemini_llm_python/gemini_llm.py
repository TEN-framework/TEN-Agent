from typing import Dict, List
import google.generativeai as genai


class GeminiLLMConfig:
    def __init__(
        self,
        api_key: str,
        max_output_tokens: int,
        model: str,
        prompt: str,
        temperature: float,
        top_k: int,
        top_p: float,
    ):
        self.api_key = api_key
        self.max_output_tokens = max_output_tokens
        self.model = model
        self.prompt = prompt
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p

    @classmethod
    def default_config(cls):
        return cls(
            api_key="",
            max_output_tokens=512,
            model="gemini-1.5-flash",
            prompt="You are a voice assistant who talks in a conversational way and can chat with me like my friends. I will speak to you in English or Chinese, and you will answer in the corrected and improved version of my text with the language I use. Don’t talk like a robot, instead I would like you to talk like a real human with emotions. I will use your answer for text-to-speech, so don’t return me any meaningless characters. I want you to be helpful, when I’m asking you for advice, give me precise, practical and useful advice instead of being vague. When giving me a list of options, express the options in a narrative way instead of bullet points.",
            temperature=1.0,
            top_k=40,
            top_p=0.95,
        )


class GeminiLLM:
    def __init__(self, config: GeminiLLMConfig):
        self.config = config
        genai.configure(api_key=self.config.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.config.model, system_instruction=self.config.prompt
        )

    def get_chat_completions_stream(self, messages: List[Dict[str, str]]):
        try:
            chat = self.model.start_chat(history=messages[0:-1])
            response = chat.send_message(
                messages[-1].get("parts"),
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=self.config.max_output_tokens,
                    temperature=self.config.temperature,
                    top_k=self.config.top_k,
                    top_p=self.config.top_p,
                ),
                stream=True,
            )

            return response
        except Exception as e:
            raise RuntimeError(f"get_chat_completions_stream failed, err: {e}") from e
