from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .task import RiskLevel


class CapabilityDescriptor(BaseModel):
    name: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    confirmation_required: bool = False
    scopes: list[str] = Field(default_factory=list)
    device_affinity: list[str] = Field(default_factory=list)
    evidence_outputs: list[str] = Field(default_factory=list)


class CapabilityManifest(BaseModel):
    name: str
    handler: str
    description: str
    risk_level: RiskLevel = RiskLevel.LOW
    confirmation_required: bool = False
    scopes: list[str] = Field(default_factory=list)
    device_affinity: list[str] = Field(default_factory=list)
    evidence_outputs: list[str] = Field(default_factory=list)


class CapabilityExecutionPayload(BaseModel):
    capability_name: str
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class CapabilityExecutionResult(BaseModel):
    capability_name: str
    action: str
    status: str
    output: str
    requires_confirmation: bool = False
