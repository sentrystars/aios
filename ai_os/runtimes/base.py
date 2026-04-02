from __future__ import annotations

from typing import Any, Protocol

from ai_os.domain import RuntimeDescriptor, RuntimeInvocation, TaskRecord
from ai_os.policy import PolicyRule
from ai_os.verification import ContextualRequirementEvaluator


class RuntimeAdapter(Protocol):
    descriptor: RuntimeDescriptor

    def prepare_task(self, task: TaskRecord) -> dict[str, Any]: ...

    def execute_task(self, task: TaskRecord) -> dict[str, Any]: ...

    def build_invocation(self, task: TaskRecord) -> RuntimeInvocation: ...

    def contributed_policy_rules(self) -> list[PolicyRule]: ...

    def contributed_verification_evaluators(self) -> list[ContextualRequirementEvaluator]: ...
