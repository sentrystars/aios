from __future__ import annotations

import json
from pathlib import Path

from ai_os.domain import CapabilityDescriptor, CapabilityExecutionPayload, CapabilityExecutionResult, CapabilityManifest

from .base import CapabilityHandler
from .local_files import LocalFilesCapability
from .messaging import MessagingCapability, NotesCapability
from .scheduling import CalendarCapability, RemindersCapability


class CapabilityRegistry:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self._manifests: dict[str, CapabilityManifest] = {}
        self._handlers: dict[str, CapabilityHandler] = {}
        self._handler_factories = {
            "local_files": lambda manifest: LocalFilesCapability(workspace_root),
            "reminders": lambda manifest: RemindersCapability(workspace_root),
            "calendar": lambda manifest: CalendarCapability(workspace_root),
            "notes": lambda manifest: NotesCapability(),
            "messaging": lambda manifest: MessagingCapability(),
        }
        self._discover()

    def list(self) -> list[CapabilityDescriptor]:
        return [handler.descriptor for handler in self._handlers.values()]

    def list_manifests(self) -> list[CapabilityManifest]:
        return list(self._manifests.values())

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        handler = self._handlers.get(payload.capability_name)
        if not handler:
            raise ValueError(f"Capability {payload.capability_name} is not registered.")
        return handler.execute(payload)

    def _discover(self) -> None:
        manifests_root = Path(__file__).resolve().parent / "manifests"
        for manifest_path in sorted(manifests_root.glob("*.json")):
            manifest = CapabilityManifest.model_validate(json.loads(manifest_path.read_text()))
            self._manifests[manifest.name] = manifest
            factory = self._handler_factories.get(manifest.handler)
            if factory is None:
                continue
            handler = factory(manifest)
            handler.descriptor = CapabilityDescriptor(
                name=manifest.name,
                description=manifest.description,
                risk_level=manifest.risk_level,
                confirmation_required=manifest.confirmation_required,
                scopes=manifest.scopes,
                device_affinity=manifest.device_affinity,
                evidence_outputs=manifest.evidence_outputs,
            )
            self._handlers[manifest.name] = handler


CapabilityBus = CapabilityRegistry
