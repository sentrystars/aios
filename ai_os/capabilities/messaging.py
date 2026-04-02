from __future__ import annotations

from ai_os.domain import CapabilityDescriptor, CapabilityExecutionPayload, CapabilityExecutionResult, RiskLevel


class NotesCapability:
    descriptor = CapabilityDescriptor(
        name="notes",
        description="Create a lightweight note payload that can later be routed to files or a notes app.",
        risk_level=RiskLevel.LOW,
        scopes=["notes:draft"],
        device_affinity=["mac_local", "ios_remote"],
        evidence_outputs=["Prepared note draft"],
    )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        title = str(payload.parameters.get("title", "Untitled"))
        body = str(payload.parameters.get("body", ""))
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="ok",
            output=f"Prepared note '{title}' with {len(body)} characters.",
        )


class AIOSLocalMessagingCapability:
    def __init__(self, *, name: str = "aios_local_messaging") -> None:
        self.descriptor = CapabilityDescriptor(
            name=name,
            description="Prepare outbound messages while enforcing confirmation for delivery.",
            risk_level=RiskLevel.HIGH,
            confirmation_required=True,
            scopes=["messaging:prepare"],
            device_affinity=["mac_local", "ios_remote"],
            evidence_outputs=["Drafted outbound message"],
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        recipient = str(payload.parameters.get("recipient", "unknown"))
        message = str(payload.parameters.get("message", ""))
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="pending_confirmation",
            output=f"Message to {recipient} prepared with {len(message)} characters.",
            requires_confirmation=True,
        )


class SystemMessagingCapability:
    descriptor = CapabilityDescriptor(
        name="system_messaging",
        description="Send or prepare messages through the host system messaging service.",
        risk_level=RiskLevel.HIGH,
        confirmation_required=True,
        scopes=["system_messaging:prepare", "system_messaging:send"],
        device_affinity=["mac_local", "ios_remote"],
        evidence_outputs=["System outbound message prepared"],
    )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="unavailable",
            output="System messaging bridge is not implemented yet. Use aios_local_messaging for local AIOS drafting.",
            requires_confirmation=True,
        )


class MessagingCapability(AIOSLocalMessagingCapability):
    def __init__(self) -> None:
        super().__init__(name="messaging")
