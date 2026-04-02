from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowManifest(BaseModel):
    name: str
    handler: str
    description: str
    entrypoint: str
    tags: list[str] = Field(default_factory=list)
