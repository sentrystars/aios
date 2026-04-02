from __future__ import annotations

import json
from pathlib import Path

from ai_os.capabilities import CapabilityRegistry
from ai_os.domain import PluginDescriptor, PluginManifest
from ai_os.runtimes import RuntimeRegistry
from ai_os.workflow_registry import WorkflowRegistry


class PluginRegistry:
    def __init__(
        self,
        manifests_root: Path,
        capability_registry: CapabilityRegistry,
        runtime_registry: RuntimeRegistry,
        workflow_registry: WorkflowRegistry,
    ) -> None:
        self._manifests_root = manifests_root
        self._capability_registry = capability_registry
        self._runtime_registry = runtime_registry
        self._workflow_registry = workflow_registry
        self._manifests: dict[str, PluginManifest] = {}
        self._discover()

    def list_manifests(self) -> list[PluginManifest]:
        return list(self._manifests.values())

    def list(self) -> list[PluginDescriptor]:
        available_capabilities = {item.name for item in self._capability_registry.list()}
        available_runtimes = {item.name for item in self._runtime_registry.list()}
        available_workflows = {item.name for item in self._workflow_registry.list_manifests()}
        descriptors: list[PluginDescriptor] = []
        for manifest in self._manifests.values():
            missing = [
                *[name for name in manifest.capabilities if name not in available_capabilities],
                *[name for name in manifest.runtimes if name not in available_runtimes],
                *[name for name in manifest.workflows if name not in available_workflows],
            ]
            notes = list(manifest.notes)
            if missing:
                notes.append(f"Missing contributions: {', '.join(sorted(missing))}")
            descriptors.append(
                PluginDescriptor(
                    name=manifest.name,
                    description=manifest.description,
                    version=manifest.version,
                    status="partial" if missing else "available",
                    runtimes=manifest.runtimes,
                    capabilities=manifest.capabilities,
                    workflows=manifest.workflows,
                    notes=notes,
                )
            )
        return descriptors

    def _discover(self) -> None:
        for manifest_path in sorted(self._manifests_root.glob("*/plugin.json")):
            manifest = PluginManifest.model_validate(json.loads(manifest_path.read_text()))
            self._manifests[manifest.name] = manifest
