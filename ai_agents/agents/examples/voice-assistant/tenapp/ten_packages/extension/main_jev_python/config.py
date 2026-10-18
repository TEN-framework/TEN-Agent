from typing import Any, Literal

from pydantic import BaseModel, Field


def default_route_question() -> dict[str, Any]:
    return {
        "type": "choice",
        "instructions": (
            "Does the latest user request need deliberate multi-step "
            "reasoning before a concise spoken answer? Do not judge by "
            "length alone."
        ),
        "criteria": {
            "fast": (
                "Greetings, small talk, and direct questions that can "
                "be answered without extended reasoning"
            ),
            "deep": (
                "Multi-step reasoning, planning with tradeoffs, or "
                "nuanced analysis that benefits from deliberate thought"
            ),
        },
    }


class ModelRoutingConfig(BaseModel):
    enabled: bool = False
    decision_dest: str = "jev"
    fast_dest: str = "llm_fast"
    deep_dest: str = "llm_deep"
    min_confidence: float = Field(default=0.8, ge=0, le=1)
    timeout_ms: int = Field(default=1200, ge=1)
    question: dict[str, Any] = Field(default_factory=default_route_question)

    def select_dest(self, decision: dict[str, Any]) -> str:
        """Use the fast model only for a valid, confident fast decision."""
        answers = decision.get("answers", {})
        route = answers.get("route", {}) if isinstance(answers, dict) else {}
        if not isinstance(route, dict):
            return self.deep_dest
        confidence = route.get("confidence")
        if (
            route.get("type") == "choice"
            and route.get("choice") == "fast"
            and isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and self.min_confidence <= confidence <= 1
        ):
            return self.fast_dest
        return self.deep_dest


class MainControlConfig(BaseModel):
    greeting: str = "Hello, I am your AI assistant."
    turn_detection_mode: Literal["segment_final", "speech_final"] = (
        "segment_final"
    )
    asr_final_fallback_ms: int = Field(default=1000, ge=1)
    model_routing: ModelRoutingConfig = Field(
        default_factory=ModelRoutingConfig
    )
