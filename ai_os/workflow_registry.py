from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ai_os.domain import WorkflowManifest
from ai_os.workflows import DeliveryCoordinator, IntakeCoordinator


class WorkflowRegistry:
    def __init__(self, manifests_root: Path, factories: dict[str, Callable[..., Any]]) -> None:
        self._manifests_root = manifests_root
        self._factories = factories
        self._manifests: dict[str, WorkflowManifest] = {}
        self._discover()

    def list_manifests(self) -> list[WorkflowManifest]:
        return list(self._manifests.values())

    def build(self, name: str, **kwargs: Any) -> Any:
        manifest = self._manifests.get(name)
        if manifest is None:
            raise ValueError(f"Workflow {name} is not registered.")
        factory = self._factories.get(manifest.handler)
        if factory is None:
            raise ValueError(f"Workflow handler {manifest.handler} is not available.")
        return factory(**kwargs)

    def _discover(self) -> None:
        for manifest_path in sorted(self._manifests_root.glob("*.json")):
            manifest = WorkflowManifest.model_validate(json.loads(manifest_path.read_text()))
            self._manifests[manifest.name] = manifest


def default_workflow_factories() -> dict[str, Callable[..., Any]]:
    return {
        "intake": lambda **kwargs: IntakeCoordinator(**kwargs),
        "delivery": lambda **kwargs: DeliveryCoordinator(**kwargs),
    }
