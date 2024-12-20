from pydantic import BaseModel


class LLMCompletionTokensDetails(BaseModel):
    accepted_prediction_tokens: int = 0
    audio_tokens: int = 0
    reasoning_tokens: int = 0
    rejected_prediction_tokens: int = 0


class LLMPromptTokensDetails(BaseModel):
    audio_tokens: int = 0
    cached_tokens: int = 0
    text_tokens: int = 0


class LLMUsage(BaseModel):
    completion_tokens: int = 0
    prompt_tokens: int = 0
    total_tokens: int = 0

    completion_tokens_details: LLMCompletionTokensDetails | None = None
    prompt_tokens_details: LLMPromptTokensDetails | None = None
