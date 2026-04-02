from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .common import utc_now


class PersonaAnchor(BaseModel):
    identity_statement: str = "A local-first personal intelligence system."
    tone: str = "clear, direct, pragmatic"
    non_negotiables: list[str] = Field(default_factory=list)
    default_planning_style: str = "goal-first"
    autonomy_preference: str = "controlled_autonomy"


class SessionContext(BaseModel):
    active_focus: list[str] = Field(default_factory=list)
    open_loops: list[str] = Field(default_factory=list)
    recent_decisions: list[str] = Field(default_factory=list)
    current_commitments: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class SelfProfile(BaseModel):
    long_term_goals: list[str] = Field(default_factory=list)
    current_phase: str = "bootstrap"
    values: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    risk_style: str = "balanced"
    boundaries: list[str] = Field(default_factory=list)
    relationship_network: list[str] = Field(default_factory=list)
    persona_anchor: PersonaAnchor = Field(default_factory=PersonaAnchor)
    session_context: SessionContext = Field(default_factory=SessionContext)
    updated_at: datetime = Field(default_factory=utc_now)
