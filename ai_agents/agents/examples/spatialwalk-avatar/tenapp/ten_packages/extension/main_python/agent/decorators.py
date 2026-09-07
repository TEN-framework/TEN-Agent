from .events import AgentEvent


def agent_event_handler(event_type: AgentEvent):
    """
    Decorator to mark a method as an Agent event handler.
    Usage:
        @agent_event_handler(ASRResultEvent)
        async def on_asr(self, event: ASRResultEvent): ...
    """

    def wrapper(func):
        setattr(func, "_agent_event_type", event_type)
        return func

    return wrapper
