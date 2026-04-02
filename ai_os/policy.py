from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ai_os.domain import ExecutionMode, PolicyRuleDescriptor, RiskLevel, TaskRecord


class LifecycleHook(str, Enum):
    BEFORE_EXECUTE = "before_execute"
    BEFORE_EXTERNAL_SIDE_EFFECT = "before_external_side_effect"


@dataclass
class PolicyContext:
    task: TaskRecord
    effect_type: str | None = None


@dataclass
class PolicyDecision:
    hook: str
    allowed: bool
    reason: str | None = None
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


PolicyCondition = Callable[[PolicyContext], bool]


@dataclass(frozen=True)
class PolicyRule:
    name: str
    hook: LifecycleHook
    condition: PolicyCondition
    allowed: bool
    terminal: bool = False
    reason: str | None = None
    notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class PolicyEngine:
    POLICY_OVERRIDE_TAG = "policy:override_confirmed"

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self._rules = rules or self._default_rules()

    def before_execute(self, task: TaskRecord) -> PolicyDecision:
        context = PolicyContext(task=task)
        default = PolicyDecision(
            hook=LifecycleHook.BEFORE_EXECUTE.value,
            allowed=True,
            metadata={
                "execution_mode": task.execution_mode.value,
                "risk_level": task.risk_level.value,
                "confirmation_required": task.execution_plan.confirmation_required,
                "matched_rules": [],
            },
        )
        return self._evaluate(LifecycleHook.BEFORE_EXECUTE, context, default)

    def before_external_side_effect(self, task: TaskRecord, effect_type: str) -> PolicyDecision:
        context = PolicyContext(task=task, effect_type=effect_type)
        default = PolicyDecision(
            hook=LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT.value,
            allowed=True,
            notes=["External side effect cleared by policy engine."],
            metadata={"effect_type": effect_type, "policy_path": "clear", "matched_rules": []},
        )
        return self._evaluate(LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT, context, default)

    def register_rule(self, rule: PolicyRule, prepend: bool = False) -> None:
        if prepend:
            self._rules.insert(0, rule)
        else:
            self._rules.append(rule)

    def extend_rules(self, rules: list[PolicyRule], prepend: bool = False) -> None:
        for rule in reversed(rules) if prepend else rules:
            self.register_rule(rule, prepend=prepend)

    def rules_for(self, hook: LifecycleHook) -> list[PolicyRule]:
        return [rule for rule in self._rules if rule.hook == hook]

    def describe_rules(self, hook: LifecycleHook | None = None) -> list[PolicyRuleDescriptor]:
        rules = self.rules_for(hook) if hook else list(self._rules)
        return [
            PolicyRuleDescriptor(
                name=rule.name,
                hook=rule.hook.value,
                allowed=rule.allowed,
                terminal=rule.terminal,
                reason=rule.reason,
                notes=list(rule.notes),
                metadata=dict(rule.metadata),
            )
            for rule in rules
        ]

    def _evaluate(self, hook: LifecycleHook, context: PolicyContext, default: PolicyDecision) -> PolicyDecision:
        matched_rules: list[PolicyRule] = []
        merged_notes = list(default.notes)
        merged_metadata = dict(default.metadata)
        final_decision = default

        for rule in self.rules_for(hook):
            if not rule.condition(context):
                continue
            matched_rules.append(rule)
            merged_notes.extend(rule.notes)
            merged_metadata.update(rule.metadata)
            merged_metadata["matched_rules"] = [item.name for item in matched_rules]
            final_decision = PolicyDecision(
                hook=hook.value,
                allowed=rule.allowed,
                reason=rule.reason,
                notes=merged_notes.copy(),
                metadata=merged_metadata.copy(),
            )
            if rule.terminal or not rule.allowed:
                return final_decision

        merged_metadata["matched_rules"] = [item.name for item in matched_rules]
        final_decision.notes = merged_notes
        final_decision.metadata = merged_metadata
        return final_decision

    @classmethod
    def _default_rules(cls) -> list[PolicyRule]:
        return [
            PolicyRule(
                name="track_high_risk_execution",
                hook=LifecycleHook.BEFORE_EXECUTE,
                condition=lambda ctx: ctx.task.risk_level == RiskLevel.HIGH,
                allowed=True,
                notes=("High-risk task execution is being tracked under policy review.",),
                metadata={"policy_path": "high_risk_tracking"},
            ),
            PolicyRule(
                name="track_confirmation_guardrail",
                hook=LifecycleHook.BEFORE_EXECUTE,
                condition=lambda ctx: ctx.task.execution_plan.confirmation_required,
                allowed=True,
                notes=("Execution plan includes a confirmation guardrail.",),
                metadata={"policy_path": "confirmation_tracking"},
            ),
            PolicyRule(
                name="delegate_message_confirmation_to_capability",
                hook=LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT,
                condition=lambda ctx: ctx.task.execution_mode == ExecutionMode.MESSAGE_DRAFT,
                allowed=True,
                terminal=True,
                notes=("Messaging tasks use capability-level confirmation rather than workflow-level blocking.",),
                metadata={"policy_path": "capability_confirmation"},
            ),
            PolicyRule(
                name="allow_approved_policy_override",
                hook=LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT,
                condition=lambda ctx: cls.POLICY_OVERRIDE_TAG in ctx.task.tags,
                allowed=True,
                terminal=True,
                notes=("Previously approved policy override allows this external side effect to proceed.",),
                metadata={"policy_path": "approved_override"},
            ),
            PolicyRule(
                name="gate_high_risk_or_confirmation_required_side_effect",
                hook=LifecycleHook.BEFORE_EXTERNAL_SIDE_EFFECT,
                condition=lambda ctx: ctx.task.risk_level == RiskLevel.HIGH or ctx.task.execution_plan.confirmation_required,
                allowed=False,
                reason="Awaiting policy confirmation before external side effect.",
                notes=("External side effect is gated because the task is high risk or explicitly requires confirmation.",),
                metadata={"policy_path": "confirmation_gate"},
            ),
        ]
