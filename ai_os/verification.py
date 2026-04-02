from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ai_os.domain import ImplementationTaskContract, RuntimeImplementationResult, TaskRecord


VerifierFn = Callable[[TaskRecord], str]
RequirementEvaluator = Callable[..., tuple[bool, str]]


@dataclass(frozen=True)
class ContextualRequirementEvaluator:
    requirement_key: str
    evaluator: RequirementEvaluator
    runtime_name: str | None = None
    deliverable_type: str | None = None
    execution_mode: str | None = None


class ContractEvaluator:
    def __init__(
        self,
        *,
        message_draft_evidence: VerifierFn,
        calendar_evidence: VerifierFn,
        reminder_evidence: VerifierFn,
        memory_evidence: VerifierFn,
    ) -> None:
        self._message_draft_evidence = message_draft_evidence
        self._calendar_evidence = calendar_evidence
        self._reminder_evidence = reminder_evidence
        self._memory_evidence = memory_evidence
        self._evaluators: dict[str, RequirementEvaluator] = {}
        self._contextual_evaluators: list[ContextualRequirementEvaluator] = []
        self._register_default_evaluators()

    def evaluate(
        self,
        *,
        task: TaskRecord,
        contract: ImplementationTaskContract,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[list[str], list[dict[str, object]]]:
        notes: list[str] = []
        assessment: list[dict[str, object]] = []
        requirements = contract.output_requirements or [
            {
                "key": expected_output.lower().replace(" ", "_"),
                "label": expected_output,
                "source": "legacy_expected_output",
            }
            for expected_output in contract.expected_outputs
        ]
        for requirement in requirements:
            if isinstance(requirement, dict):
                requirement_key = str(requirement.get("key", "legacy_output"))
                requirement_label = str(requirement.get("label", requirement_key))
                requirement_source = str(requirement.get("source", "legacy_expected_output"))
                requirement_required = bool(requirement.get("required", True))
            else:
                requirement_key = requirement.key
                requirement_label = requirement.label
                requirement_source = requirement.source
                requirement_required = requirement.required
            satisfied, detail = self._assess_requirement(
                requirement_key=requirement_key,
                requirement_label=requirement_label,
                requirement_source=requirement_source,
                task=task,
                contract=contract,
                implementation_result=implementation_result,
                human_evidence=human_evidence,
            )
            prefix = (
                "Contract output satisfied"
                if satisfied
                else "Missing contract output"
                if requirement_required
                else "Optional contract output not satisfied"
            )
            notes.append(f"{prefix}: {detail}")
            assessment.append(
                {
                    "key": requirement_key,
                    "expected_output": requirement_label,
                    "source": requirement_source,
                    "required": requirement_required,
                    "satisfied": satisfied,
                    "detail": detail,
                }
            )
        if contract.acceptance_criteria:
            notes.append(f"Contract acceptance criteria reviewed: {len(contract.acceptance_criteria)}")
        return notes, assessment

    @staticmethod
    def verification_summary(contract_assessment: list[dict[str, object]]) -> dict[str, object]:
        unmet_outputs = [
            str(item["expected_output"])
            for item in contract_assessment
            if item.get("required", True) and not item.get("satisfied")
        ]
        unmet_output_keys = [
            str(item["key"])
            for item in contract_assessment
            if item.get("required", True) and not item.get("satisfied")
        ]
        satisfied_outputs = [
            str(item["expected_output"])
            for item in contract_assessment
            if item.get("satisfied")
        ]
        satisfied_output_keys = [
            str(item["key"])
            for item in contract_assessment
            if item.get("satisfied")
        ]
        return {
            "unmet_contract_outputs": unmet_outputs,
            "unmet_contract_output_keys": unmet_output_keys,
            "satisfied_contract_outputs": satisfied_outputs,
            "satisfied_contract_output_keys": satisfied_output_keys,
            "contract_output_assessment": contract_assessment,
        }

    def _assess_requirement(
        self,
        *,
        requirement_key: str,
        requirement_label: str,
        requirement_source: str,
        task: TaskRecord,
        contract: ImplementationTaskContract,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        evaluator = self._resolve_evaluator(
            requirement_key=requirement_key,
            task=task,
            contract=contract,
        )
        if evaluator is not None:
            return evaluator(
                requirement_label=requirement_label,
                task=task,
                implementation_result=implementation_result,
                human_evidence=human_evidence,
            )
        return (True, f"{requirement_label} via {requirement_source}")

    def register_evaluator(self, requirement_key: str, evaluator: RequirementEvaluator) -> None:
        self._evaluators[requirement_key] = evaluator

    def register_evaluators(self, evaluators: dict[str, RequirementEvaluator]) -> None:
        self._evaluators.update(evaluators)

    def register_contextual_evaluator(
        self,
        requirement_key: str,
        evaluator: RequirementEvaluator,
        *,
        runtime_name: str | None = None,
        deliverable_type: str | None = None,
        execution_mode: str | None = None,
    ) -> None:
        self._contextual_evaluators.append(
            ContextualRequirementEvaluator(
                requirement_key=requirement_key,
                evaluator=evaluator,
                runtime_name=runtime_name,
                deliverable_type=deliverable_type,
                execution_mode=execution_mode,
            )
        )

    def _register_default_evaluators(self) -> None:
        self.register_evaluators(
            {
                "changed_files": self._evaluate_changed_files_requirement,
                "commands_or_tests": self._evaluate_commands_or_tests_requirement,
                "verification_evidence": self._evaluate_verification_evidence_requirement,
                "artifact_or_code_change": self._evaluate_artifact_or_code_change_requirement,
                "message_draft": self._evaluate_message_draft_requirement,
                "calendar_event": self._evaluate_calendar_event_requirement,
                "reminder": self._evaluate_reminder_requirement,
                "memory_record": self._evaluate_memory_record_requirement,
            }
        )

    def _resolve_evaluator(
        self,
        *,
        requirement_key: str,
        task: TaskRecord,
        contract: ImplementationTaskContract,
    ) -> RequirementEvaluator | None:
        best_match: tuple[int, RequirementEvaluator] | None = None
        runtime_name = task.runtime_name or task.execution_plan.runtime_name
        execution_mode = task.execution_mode.value
        for candidate in self._contextual_evaluators:
            if candidate.requirement_key != requirement_key:
                continue
            if candidate.runtime_name and candidate.runtime_name != runtime_name:
                continue
            if candidate.deliverable_type and candidate.deliverable_type != contract.deliverable_type:
                continue
            if candidate.execution_mode and candidate.execution_mode != execution_mode:
                continue
            specificity = sum(
                value is not None
                for value in (candidate.runtime_name, candidate.deliverable_type, candidate.execution_mode)
            )
            if best_match is None or specificity > best_match[0]:
                best_match = (specificity, candidate.evaluator)
        if best_match is not None:
            return best_match[1]
        return self._evaluators.get(requirement_key)

    @staticmethod
    def _evaluate_changed_files_requirement(
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        output_count = len(implementation_result.changed_files) + len(task.artifact_paths)
        return (output_count > 0, f"{requirement_label} ({output_count} outputs)")

    @staticmethod
    def _evaluate_commands_or_tests_requirement(
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        count = len(implementation_result.tests_run) + len(implementation_result.commands_run)
        return (count > 0, f"{requirement_label} ({count} entries)")

    @staticmethod
    def _evaluate_verification_evidence_requirement(
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        evidence_count = len(implementation_result.verification_evidence) + len(human_evidence)
        return (evidence_count > 0, f"{requirement_label} ({evidence_count} entries)")

    @staticmethod
    def _evaluate_artifact_or_code_change_requirement(
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        count = len(task.artifact_paths) + len(implementation_result.changed_files)
        return (count > 0, f"{requirement_label} ({count} outputs)")

    def _evaluate_message_draft_requirement(
        self,
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        has_message = not self._message_draft_evidence(task).startswith("Missing")
        return (has_message, requirement_label)

    def _evaluate_calendar_event_requirement(
        self,
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        has_event = self._calendar_evidence(task) == "Calendar event scheduled"
        return (has_event, requirement_label)

    def _evaluate_reminder_requirement(
        self,
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        has_reminder = self._reminder_evidence(task) == "Reminder scheduled"
        return (has_reminder, requirement_label)

    def _evaluate_memory_record_requirement(
        self,
        *,
        requirement_label: str,
        task: TaskRecord,
        implementation_result: RuntimeImplementationResult,
        human_evidence: list[str],
    ) -> tuple[bool, str]:
        has_memory = self._memory_evidence(task) == "Memory record created"
        return (has_memory, requirement_label)
