from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_os.domain import RuntimeDescriptor, RuntimeInvocation, RuntimeManifest, TaskRecord
from ai_os.policy import PolicyRule

from .base import RuntimeAdapter
from .claude_code import ClaudeCodeRuntime


class RuntimeRegistry:
    def __init__(self, workspace_root: Path, app_root: Path) -> None:
        self.workspace_root = workspace_root
        self.app_root = app_root
        self._manifests: dict[str, RuntimeManifest] = {}
        self._runtimes: dict[str, RuntimeAdapter] = {}
        self._adapter_factories = {
            "claude-code": lambda manifest: ClaudeCodeRuntime(workspace_root=workspace_root, app_root=app_root),
        }
        self._discover()

    def list(self) -> list[RuntimeDescriptor]:
        return [runtime.descriptor for runtime in self._runtimes.values()]

    def list_manifests(self) -> list[RuntimeManifest]:
        return list(self._manifests.values())

    def get(self, name: str) -> RuntimeAdapter:
        runtime = self._runtimes.get(name)
        if not runtime:
            raise ValueError(f"Runtime {name} is not registered.")
        return runtime

    def prepare_task(self, runtime_name: str, task: TaskRecord) -> dict[str, Any]:
        return self.get(runtime_name).prepare_task(task)

    def execute_task(self, runtime_name: str, task: TaskRecord) -> dict[str, Any]:
        return self.get(runtime_name).execute_task(task)

    def build_invocation(self, runtime_name: str, task: TaskRecord) -> RuntimeInvocation:
        return self.get(runtime_name).build_invocation(task)

    def contributed_policy_rules(self) -> list[PolicyRule]:
        rules: list[PolicyRule] = []
        for runtime in self._runtimes.values():
            rules.extend(runtime.contributed_policy_rules())
        return rules

    def _discover(self) -> None:
        manifests_root = self.app_root / "runtimes"
        for manifest_path in sorted(manifests_root.glob("*/runtime.json")):
            manifest = RuntimeManifest.model_validate(json.loads(manifest_path.read_text()))
            self._manifests[manifest.name] = manifest
            factory = self._adapter_factories.get(manifest.adapter)
            if factory is None:
                continue
            runtime = factory(manifest)
            runtime.descriptor.description = manifest.description
            runtime.descriptor.runtime_type = manifest.runtime_type
            runtime.descriptor.supported_capabilities = manifest.supported_capabilities
            runtime.descriptor.notes = [*runtime.descriptor.notes, *manifest.notes]
            self._runtimes[manifest.name] = runtime
