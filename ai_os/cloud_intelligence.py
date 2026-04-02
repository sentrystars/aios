from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib import error, request

from pydantic import BaseModel, Field

from ai_os.domain import ExecutionMode, IntentType, SelfProfile


class CloudIntentHint(BaseModel):
    intent_type: IntentType | None = None
    urgency: int | None = Field(default=None, ge=1, le=5)
    needs_confirmation: bool | None = None
    execution_mode: ExecutionMode | None = None
    runtime_name: str | None = None
    explicit_constraints: list[str] = Field(default_factory=list)
    inferred_constraints: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    time_horizon: str | None = None
    continuation_preference: str | None = None
    success_shape: str | None = None
    suggested_task_tags: list[str] = Field(default_factory=list)
    rationale: str | None = None
    provider: str = "deepseek"
    model: str = "deepseek-chat"


@dataclass
class DeepSeekConversationIntelligence:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        self._cache: dict[str, CloudIntentHint] = {}

    @classmethod
    def from_env(cls) -> DeepSeekConversationIntelligence | None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            timeout_seconds=float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "15")),
        )

    def analyze(self, text: str, profile: SelfProfile) -> CloudIntentHint | None:
        cache_key = f"{text}\n{profile.current_phase}\n{profile.risk_style}\n{'|'.join(profile.boundaries)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "text": text,
                            "self_profile": {
                                "current_phase": profile.current_phase,
                                "risk_style": profile.risk_style,
                                "boundaries": profile.boundaries,
                                "relationship_network": profile.relationship_network,
                                "long_term_goals": profile.long_term_goals,
                            },
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 700,
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return None
        try:
            content = raw["choices"][0]["message"]["content"]
            hint = CloudIntentHint.model_validate(json.loads(content))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError):
            return None
        self._cache[cache_key] = hint
        return hint

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are the intent-understanding layer for an AI operating system. "
            "Return json only. "
            "Classify the user's request and infer execution hints conservatively. "
            "Use this JSON schema exactly: "
            "{"
            "\"intent_type\": \"question|task|clarification|routine|conflict|null\", "
            "\"urgency\": 1, "
            "\"needs_confirmation\": false, "
            "\"execution_mode\": \"file_artifact|memory_capture|message_draft|reminder|calendar_event|null\", "
            "\"runtime_name\": \"string or null\", "
            "\"explicit_constraints\": [\"...\"], "
            "\"inferred_constraints\": [\"...\"], "
            "\"stakeholders\": [\"...\"], "
            "\"time_horizon\": \"today|near_term|long_term|unspecified|null\", "
            "\"continuation_preference\": \"string or null\", "
            "\"success_shape\": \"string or null\", "
            "\"suggested_task_tags\": [\"...\"], "
            "\"rationale\": \"short explanation\", "
            "\"provider\": \"deepseek\", "
            "\"model\": \"deepseek-chat\""
            "}. "
            "Prefer null instead of inventing uncertain fields. "
            "If the request is about deep work or focused work blocks, calendar_event is often appropriate. "
            "If the request is about coding, repos, refactors, implementations, or runtime work, runtime_name can be claude-code."
        )
