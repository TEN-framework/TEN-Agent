from pydantic import BaseModel


class MainControlConfig(BaseModel):
    greeting: str = "Hello, I am your AI assistant."
    # A tool called on every final user turn instead of being offered to the LLM.
    context_tool: str = ""
