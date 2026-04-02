from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeDescriptor(BaseModel):
    name: str
    description: str
    status: str = "available"
    runtime_type: str = "adapter"
    root_path: str | None = None
    supported_capabilities: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeManifest(BaseModel):
    name: str
    adapter: str
    description: str
    runtime_type: str = "adapter"
    supported_capabilities: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeInvocation(BaseModel):
    runtime: str
    status: str = "ready"
    launch_command: str
    launch_args: list[str] = Field(default_factory=list)
    working_directory: str
    environment_hints: dict[str, str] = Field(default_factory=dict)
    prompt: str
    invocation_mode: str = "interactive_handoff"
    notes: list[str] = Field(default_factory=list)
