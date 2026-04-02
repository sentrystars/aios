from __future__ import annotations

from typing import Protocol

from ai_os.domain import CapabilityDescriptor, CapabilityExecutionPayload, CapabilityExecutionResult


class CapabilityHandler(Protocol):
    descriptor: CapabilityDescriptor

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult: ...
