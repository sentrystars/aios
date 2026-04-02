from __future__ import annotations

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    name: str
    description: str
    version: str = "0.1.0"
    runtimes: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PluginDescriptor(BaseModel):
    name: str
    description: str
    version: str = "0.1.0"
    status: str = "available"
    runtimes: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
