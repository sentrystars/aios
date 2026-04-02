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
    task_contract: dict[str, object] = Field(default_factory=dict)
    invocation_mode: str = "interactive_handoff"
    notes: list[str] = Field(default_factory=list)


class RuntimeImplementationResult(BaseModel):
    status: str
    changed_files: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    tests_passed: list[str] = Field(default_factory=list)
    tests_failed: list[str] = Field(default_factory=list)
    diff_summary: str = ""
    verification_evidence: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    suggested_next_step: str = ""
