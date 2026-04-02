from __future__ import annotations

import json
from pathlib import Path

from ai_os.domain import CapabilityDescriptor, CapabilityExecutionPayload, CapabilityExecutionResult, RiskLevel


class LocalFilesCapability:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.descriptor = CapabilityDescriptor(
            name="local_files",
            description="Read, write, and inspect files inside the workspace root only.",
            risk_level=RiskLevel.MEDIUM,
            scopes=["files:read", "files:write", "files:list"],
            device_affinity=["mac_local"],
            evidence_outputs=["File read or written inside workspace root"],
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        target = self._resolve_target(str(payload.parameters.get("path", "")))
        if payload.action == "write_text":
            content = str(payload.parameters.get("content", ""))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Wrote {len(content)} characters to {target.relative_to(self.workspace_root)}.",
            )
        if payload.action == "read_text":
            if not target.exists():
                raise ValueError(f"File {target.relative_to(self.workspace_root)} does not exist.")
            content = target.read_text(encoding="utf-8")
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=content,
            )
        if payload.action == "list_dir":
            directory = target if target.suffix == "" or target.is_dir() else target.parent
            if not directory.exists():
                raise ValueError(f"Directory {directory.relative_to(self.workspace_root)} does not exist.")
            entries = sorted(path.name for path in directory.iterdir())
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps(entries),
            )
        if payload.action == "exists":
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output="true" if target.exists() else "false",
            )
        raise ValueError(f"Unsupported local_files action: {payload.action}")

    def _resolve_target(self, raw_path: str) -> Path:
        if not raw_path:
            raise ValueError("Capability local_files requires a path parameter.")
        candidate = (self.workspace_root / raw_path).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError("Path escapes the workspace root.") from exc
        return candidate
