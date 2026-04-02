from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

from ai_os.domain import RuntimeDescriptor, RuntimeInvocation, TaskRecord
from ai_os.policy import LifecycleHook, PolicyRule


class ClaudeCodeRuntime:
    def __init__(
        self,
        workspace_root: Path,
        app_root: Path,
        command_runner: Callable[[RuntimeInvocation], dict[str, Any]] | None = None,
        command_exists: Callable[[str], str | None] | None = None,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.runtime_root = (app_root / "runtimes" / "claude-code").resolve()
        self.command_runner = command_runner
        self.command_exists = command_exists or shutil.which
        status = "available" if self.runtime_root.exists() else "unavailable"
        notes = [
            "Adapter can execute Claude Code in print mode when the local claude CLI is available.",
        ]
        if status == "available":
            notes.append("Claude Code subtree is present in the repository.")
        else:
            notes.append("Claude Code subtree is missing from the repository.")
        self.descriptor = RuntimeDescriptor(
            name="claude-code",
            description="Development runtime adapter for repository exploration, code edits, shell tasks, and git workflows.",
            status=status,
            runtime_type="development",
            root_path=str(self.runtime_root),
            supported_capabilities=["code.execute", "repo.explore", "git.workflow"],
            notes=notes,
        )

    def prepare_task(self, task: TaskRecord) -> dict[str, Any]:
        invocation = self.build_invocation(task)
        return {
            "runtime": self.descriptor.name,
            "status": self.descriptor.status,
            "workspace_root": str(self.workspace_root),
            "runtime_root": str(self.runtime_root),
            "command_preview": self._command_preview(invocation),
            "prompt_preview": invocation.prompt,
        }

    def execute_task(self, task: TaskRecord) -> dict[str, Any]:
        invocation = self.build_invocation(task)
        execution = self._run_invocation(invocation)
        prompt_lines = invocation.prompt.splitlines()
        artifact_lines = [
            f"# Runtime Execution: {self.descriptor.name}",
            "",
            f"- Task ID: {task.id}",
            f"- Objective: {task.objective}",
            f"- Runtime Status: {self.descriptor.status}",
            f"- Invocation Mode: {invocation.invocation_mode}",
            f"- Command Preview: {self._command_preview(invocation)}",
            f"- Working Directory: {invocation.working_directory}",
            f"- Execution Status: {execution['execution_status']}",
            "",
            "## Prompt Preview",
            *prompt_lines,
            "",
            "## Environment Hints",
            *[f"- {key}={value}" for key, value in invocation.environment_hints.items()],
            "",
            "## Command Result",
            f"- Exit Code: {execution['exit_code'] if execution['exit_code'] is not None else 'n/a'}",
            f"- Live Execution: {'yes' if execution['live_execution'] else 'no'}",
            "",
            "### Stdout",
            execution["stdout"] or "(empty)",
            "",
            "### Stderr",
            execution["stderr"] or "(empty)",
            "",
            "## Execution Notes",
            "- Runtime adapter prefers `claude -p` print mode for non-interactive execution.",
            "- If the local `claude` CLI is unavailable, the adapter falls back to a handoff artifact.",
        ]
        return {
            "runtime": self.descriptor.name,
            "status": self.descriptor.status,
            "workspace_root": str(self.workspace_root),
            "runtime_root": str(self.runtime_root),
            "command_preview": self._command_preview(invocation),
            "prompt_preview": invocation.prompt,
            "invocation": invocation.model_dump(mode="json"),
            **execution,
            "artifact_content": "\n".join(artifact_lines),
            "summary": (
                f"Executed Claude Code print-mode command for {task.objective}"
                if execution["live_execution"]
                else f"Prepared Claude Code handoff bundle for {task.objective}"
            ),
        }

    def build_invocation(self, task: TaskRecord) -> RuntimeInvocation:
        prompt = "\n".join(self._task_lines(task))
        return RuntimeInvocation(
            runtime=self.descriptor.name,
            status="ready" if self.descriptor.status == "available" else "degraded",
            launch_command="claude",
            launch_args=["-p"],
            working_directory=str(self.workspace_root),
            environment_hints={
                "AI_OS_RUNTIME": self.descriptor.name,
                "AI_OS_TASK_ID": task.id,
                "CLAUDE_CODE_ROOT": str(self.runtime_root),
            },
            prompt=prompt,
            invocation_mode="print_mode",
            notes=[
                "Uses Claude Code print mode (`claude -p`) for non-interactive execution when available.",
                "Environment hints describe the execution context expected by the runtime adapter.",
            ],
        )

    def contributed_policy_rules(self) -> list[PolicyRule]:
        return [
            PolicyRule(
                name="claude_code_runtime_tracks_code_execution",
                hook=LifecycleHook.BEFORE_EXECUTE,
                condition=lambda ctx: ctx.task.runtime_name == self.descriptor.name
                or ctx.task.execution_plan.runtime_name == self.descriptor.name,
                allowed=True,
                notes=("Claude Code runtime selected for this task; execution should preserve repo-safe runtime handoff semantics.",),
                metadata={"policy_path": "runtime:claude_code", "runtime_name": self.descriptor.name},
            )
        ]

    @staticmethod
    def _task_lines(task: TaskRecord) -> list[str]:
        lines = [
            f"Objective: {task.objective}",
            f"Execution mode: {task.execution_mode.value}",
            f"Risk level: {task.risk_level.value}",
        ]
        if task.success_criteria:
            lines.append("Success criteria:")
            lines.extend([f"- {item}" for item in task.success_criteria])
        if task.subtasks:
            lines.append("Planned subtasks:")
            lines.extend([f"- {item}" for item in task.subtasks])
        return lines

    @staticmethod
    def _command_preview(invocation: RuntimeInvocation) -> str:
        if invocation.launch_args:
            return " ".join([invocation.launch_command, *invocation.launch_args])
        return invocation.launch_command

    def _run_invocation(self, invocation: RuntimeInvocation) -> dict[str, Any]:
        if self.command_runner is not None:
            result = self.command_runner(invocation)
            return {
                "execution_status": result.get("execution_status", "completed"),
                "exit_code": result.get("exit_code"),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "executed_command": result.get("executed_command", self._command_preview(invocation)),
                "live_execution": bool(result.get("live_execution", True)),
            }

        if not self.command_exists(invocation.launch_command):
            return {
                "execution_status": "not_installed",
                "exit_code": None,
                "stdout": "",
                "stderr": "Claude CLI is not installed or not available on PATH.",
                "executed_command": self._command_preview(invocation),
                "live_execution": False,
            }

        env = os.environ.copy()
        env.update(invocation.environment_hints)
        command = [invocation.launch_command, *invocation.launch_args, invocation.prompt]
        completed = subprocess.run(
            command,
            cwd=invocation.working_directory,
            env=env,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        return {
            "execution_status": "completed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "executed_command": self._command_preview(invocation),
            "live_execution": True,
        }
