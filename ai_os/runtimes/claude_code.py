from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable

from ai_os.domain import RuntimeDescriptor, RuntimeImplementationResult, RuntimeInvocation, TaskRecord
from ai_os.policy import LifecycleHook, PolicyRule
from ai_os.verification import ContextualRequirementEvaluator


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
            "task_contract": invocation.task_contract,
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
            "## Task Contract",
            *[f"- {key}: {value}" for key, value in invocation.task_contract.items()],
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
            "task_contract": invocation.task_contract,
            "implementation_result": self._implementation_result(task, execution),
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
            task_contract=self._task_contract(task),
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

    def contributed_verification_evaluators(self) -> list[ContextualRequirementEvaluator]:
        return [
            ContextualRequirementEvaluator(
                requirement_key="commands_or_tests",
                evaluator=self._evaluate_commands_or_tests_for_code_runtime,
                runtime_name=self.descriptor.name,
                deliverable_type="code_change",
            )
        ]

    @staticmethod
    def _evaluate_commands_or_tests_for_code_runtime(
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
        **_: Any,
    ) -> tuple[bool, str]:
        if implementation_result.tests_failed:
            return (False, f"{requirement_label} ({len(implementation_result.tests_failed)} failed tests)")
        test_count = len(implementation_result.tests_run) + len(implementation_result.tests_passed)
        if test_count > 0:
            return (True, f"{requirement_label} ({test_count} test signals)")
        command_count = len(implementation_result.commands_run)
        return (command_count > 0, f"{requirement_label} ({command_count} command signals)")

    @staticmethod
    def _task_lines(task: TaskRecord) -> list[str]:
        lines = [
            f"Objective: {task.objective}",
            f"Execution mode: {task.execution_mode.value}",
            f"Risk level: {task.risk_level.value}",
        ]
        if task.implementation_contract:
            lines.extend(
                [
                    "Implementation contract:",
                    f"- Summary: {task.implementation_contract.summary}",
                    f"- Deliverable type: {task.implementation_contract.deliverable_type}",
                    f"- Scope: {task.implementation_contract.execution_scope}",
                ]
            )
            if task.implementation_contract.acceptance_criteria:
                lines.append("Acceptance criteria:")
                lines.extend([f"- {item}" for item in task.implementation_contract.acceptance_criteria])
            if task.implementation_contract.constraints:
                lines.append("Constraints:")
                lines.extend([f"- {item}" for item in task.implementation_contract.constraints])
            if task.implementation_contract.repo_instructions:
                lines.append("Repo instructions:")
                lines.extend([f"- {item}" for item in task.implementation_contract.repo_instructions])
        if task.success_criteria:
            lines.append("Success criteria:")
            lines.extend([f"- {item}" for item in task.success_criteria])
        if task.subtasks:
            lines.append("Planned subtasks:")
            lines.extend([f"- {item}" for item in task.subtasks])
        return lines

    @staticmethod
    def _task_contract(task: TaskRecord) -> dict[str, Any]:
        if not task.implementation_contract:
            return {}
        return task.implementation_contract.model_dump(mode="json")

    @staticmethod
    def _implementation_result(task: TaskRecord, execution: dict[str, Any]) -> dict[str, Any]:
        evidence = list(task.success_criteria)
        if task.execution_plan.expected_evidence:
            evidence.extend(task.execution_plan.expected_evidence)
        tests_run = ClaudeCodeRuntime._collect_test_signals(task, execution)
        changed_files = ClaudeCodeRuntime._collect_changed_files(execution)
        failed = execution.get("execution_status") == "failed"
        test_summary = ClaudeCodeRuntime._summarize_test_outcome(execution)
        diff_summary = ClaudeCodeRuntime._summarize_diff(changed_files)
        result = RuntimeImplementationResult(
            status=str(execution.get("execution_status", "unknown")),
            changed_files=changed_files,
            commands_run=[execution.get("executed_command")] if execution.get("executed_command") else [],
            tests_run=tests_run,
            tests_passed=test_summary["passed"],
            tests_failed=test_summary["failed"],
            diff_summary=diff_summary,
            verification_evidence=evidence,
            blockers=[execution["stderr"]] if failed and execution.get("stderr") else [],
            suggested_next_step=(
                f"Replan task: {task.objective}" if failed else "Verify runtime output and update the task evidence."
            ),
        )
        return result.model_dump(mode="json")

    @staticmethod
    def _collect_test_signals(task: TaskRecord, execution: dict[str, Any]) -> list[str]:
        tests_run: list[str] = []
        for item in task.subtasks:
            lowered = item.lower()
            if "test" in lowered or "verify" in lowered:
                tests_run.append(item)
        combined_output = "\n".join([execution.get("stdout", ""), execution.get("stderr", ""), execution.get("executed_command", "")])
        for line in combined_output.splitlines():
            lowered = line.lower().strip()
            if not lowered:
                continue
            if any(token in lowered for token in ("pytest", "unittest", "npm test", "swift test", "cargo test", "go test", "test ")):
                tests_run.append(line.strip())
        return ClaudeCodeRuntime._dedupe(tests_run)

    @staticmethod
    def _collect_changed_files(execution: dict[str, Any]) -> list[str]:
        explicit = execution.get("changed_files", [])
        if isinstance(explicit, list) and explicit:
            return ClaudeCodeRuntime._dedupe([str(item) for item in explicit if item])
        combined_output = "\n".join([execution.get("stdout", ""), execution.get("stderr", "")])
        pattern = re.compile(r"(?<!\w)([A-Za-z0-9_./-]+\.(?:py|ts|tsx|js|jsx|swift|md|json|toml|yaml|yml|sh|txt))(?!\w)")
        candidates = pattern.findall(combined_output)
        return ClaudeCodeRuntime._dedupe(candidates)

    @staticmethod
    def _summarize_test_outcome(execution: dict[str, Any]) -> dict[str, list[str]]:
        combined_output = "\n".join([execution.get("stdout", ""), execution.get("stderr", "")])
        passed: list[str] = []
        failed: list[str] = []
        for line in combined_output.splitlines():
            lowered = line.lower().strip()
            if not lowered:
                continue
            if any(token in lowered for token in ("passed", "ok", "all tests passed")) and "test" in lowered:
                passed.append(line.strip())
            if any(token in lowered for token in ("failed", "error", "traceback")) and "test" in lowered:
                failed.append(line.strip())
        return {
            "passed": ClaudeCodeRuntime._dedupe(passed),
            "failed": ClaudeCodeRuntime._dedupe(failed),
        }

    @staticmethod
    def _summarize_diff(changed_files: list[str]) -> str:
        if not changed_files:
            return "No changed files detected."
        preview = ", ".join(changed_files[:3])
        if len(changed_files) > 3:
            preview += f", +{len(changed_files) - 3} more"
        return f"{len(changed_files)} changed files: {preview}"

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

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
        changed_files = self._git_changed_files(invocation.working_directory)
        return {
            "execution_status": "completed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "executed_command": self._command_preview(invocation),
            "live_execution": True,
            "changed_files": changed_files,
        }

    @staticmethod
    def _git_changed_files(working_directory: str) -> list[str]:
        try:
            completed = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=working_directory,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if completed.returncode != 0:
            return []
        return ClaudeCodeRuntime._dedupe([line.strip() for line in completed.stdout.splitlines() if line.strip()])
