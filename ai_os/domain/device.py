from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .common import utc_now


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    UNAVAILABLE = "unavailable"


class DeviceRecord(BaseModel):
    id: str
    name: str
    device_class: str
    status: DeviceStatus = DeviceStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    last_seen_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceUpsertPayload(BaseModel):
    id: str
    name: str
    device_class: str
    status: DeviceStatus = DeviceStatus.ACTIVE
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
