from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .common import utc_now


class MemoryType(str, Enum):
    PROFILE = "profile"
    TASK = "task"
    KNOWLEDGE = "knowledge"
    REFLECTION = "reflection"
    LEARNING = "learning"


class MemoryLayer(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryRecord(BaseModel):
    id: str
    memory_type: MemoryType
    layer: MemoryLayer = MemoryLayer.SEMANTIC
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str = "user"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    freshness: str = "active"
    related_goal_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class MemoryCreatePayload(BaseModel):
    memory_type: MemoryType
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    layer: MemoryLayer = MemoryLayer.SEMANTIC
    source: str = "user"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    freshness: str = "active"
    related_goal_ids: list[str] = Field(default_factory=list)


class MemoryRecallItem(BaseModel):
    memory_id: str
    title: str
    layer: MemoryLayer
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class MemoryRecallResponse(BaseModel):
    query: str
    items: list[MemoryRecallItem] = Field(default_factory=list)


class LearningInsight(BaseModel):
    memory_id: str
    title: str
    category: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class LearningRecallResponse(BaseModel):
    query: str
    items: list[LearningInsight] = Field(default_factory=list)
