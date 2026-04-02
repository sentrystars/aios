from __future__ import annotations

import json

from ai_os.domain import EventRecord, TimelineItem
from ai_os.storage import EventRepository

class EventQueryService:
    def __init__(self, event_repo: EventRepository) -> None:
        self.event_repo = event_repo

    def list_recent(self, limit: int = 100) -> list[EventRecord]:
        return self.event_repo.list_recent(limit)

    def list_for_task(self, task_id: str, limit: int = 100) -> list[EventRecord]:
        return self.event_repo.list_for_task(task_id, limit)

    def list_for_execution_run(self, run_id: str, limit: int = 100) -> list[EventRecord]:
        return self.event_repo.list_for_execution_run(run_id, limit)

    def task_timeline(self, task_id: str, limit: int = 100) -> list[TimelineItem]:
        events = self.event_repo.list_for_task(task_id, limit)
        return [self._to_timeline_item(event) for event in reversed(events)]

    def execution_run_timeline(self, run_id: str, limit: int = 100) -> list[TimelineItem]:
        events = self.event_repo.list_for_execution_run(run_id, limit)
        return [self._to_timeline_item(event) for event in reversed(events)]

    def self_timeline(self, limit: int = 100) -> list[TimelineItem]:
        events = [event for event in self.event_repo.list_recent(limit * 3) if event.event_type == "self.updated"][:limit]
        return [self._to_timeline_item(event) for event in reversed(events)]

    @staticmethod
    def _to_timeline_item(event: EventRecord) -> TimelineItem:
        payload = event.payload
        mapping = {
            "task.created": ("captured", "Task Captured", payload.get("objective", "Task created")),
            "task.planned": ("planned", "Task Planned", f"Execution mode: {payload.get('execution_mode', 'unknown')}"),
            "task.executing": ("executing", "Execution Started", "Task moved into execution."),
            "task.executed": ("executing", "Execution Produced Output", EventQueryService._execution_detail(payload)),
            "task.blocked_by_policy": ("blocked", "Blocked By Policy", EventQueryService._policy_block_detail(payload)),
            "task.resumed_from_reminder": ("coordination", "Reminder Resumed Task", EventQueryService._reminder_resume_detail(payload)),
            "task.confirmed": ("confirmed", "User Decision Recorded", EventQueryService._confirmation_detail(payload)),
            "task.verified": ("verified", "Verification Completed", f"Status: {payload.get('status', 'unknown')}"),
            "candidate.accepted": ("coordination", "Candidate Accepted", EventQueryService._candidate_detail(payload)),
            "candidate.auto_accepted": ("coordination", "Candidate Auto-Accepted", EventQueryService._candidate_detail(payload)),
            "candidate.auto_accept_batch_completed": ("coordination", "Candidate Auto-Accept Batch Completed", EventQueryService._candidate_batch_detail(payload)),
            "candidate.deferred": ("coordination", "Candidate Deferred", EventQueryService._candidate_defer_detail(payload)),
            "scheduler.stalled_task.escalated": ("coordination", "Stalled Task Escalated", EventQueryService._stalled_escalation_detail(payload)),
            "scheduler.stalled_task.followup_created": ("coordination", "Stalled Task Follow-Up Created", EventQueryService._stalled_followup_detail(payload)),
            "scheduler.stalled_task.reminder_created": ("coordination", "Stalled Task Reminder Created", EventQueryService._stalled_task_detail(payload)),
            "scheduler.tick.completed": ("coordination", "Scheduler Tick Completed", EventQueryService._scheduler_tick_detail(payload)),
            "execution_run.started": ("run", "Execution Run Started", EventQueryService._run_detail(payload)),
            "execution_run.updated": ("run", "Execution Run Updated", EventQueryService._run_update_detail(payload)),
            "execution_run.completed": ("run", "Execution Run Completed", EventQueryService._run_completion_detail(payload)),
            "memory.created": ("memory", "Memory Stored", payload.get("title", "Memory created")),
            "memory.reflection_created": ("reflection", "Reflection Stored", payload.get("title", "Reflection created")),
            "relation.created": ("relation", "Relation Recorded", EventQueryService._relation_detail(payload)),
            "self.updated": ("self", "Self Profile Updated", EventQueryService._self_detail(payload)),
        }
        phase, title, detail = mapping.get(
            event.event_type,
            ("event", event.event_type.replace(".", " ").title(), json.dumps(payload, ensure_ascii=True)),
        )
        return TimelineItem(
            timestamp=event.created_at,
            phase=phase,
            title=title,
            detail=detail,
            event_type=event.event_type,
        )

    @staticmethod
    def _execution_detail(payload: dict) -> str:
        artifact_paths = payload.get("artifact_paths") or []
        if artifact_paths:
            return f"Artifacts: {', '.join(artifact_paths)}"
        executor = payload.get("executor", "unknown")
        return f"Executor: {executor}"

    @staticmethod
    def _confirmation_detail(payload: dict) -> str:
        if payload.get("approved"):
            return payload.get("note", "User approved the task.")
        return payload.get("note", "User rejected the task.")

    @staticmethod
    def _policy_block_detail(payload: dict) -> str:
        return payload.get("reason", "Execution blocked by policy.")

    @staticmethod
    def _self_detail(payload: dict) -> str:
        changes = payload.get("changes", {})
        if not changes:
            return "Self profile saved with no material field changes."
        changed_fields = ", ".join(sorted(changes.keys()))
        return f"Changed fields: {changed_fields}"

    @staticmethod
    def _relation_detail(payload: dict) -> str:
        return (
            f"{payload.get('source_type')}:{payload.get('source_id')} "
            f"{payload.get('relation_type')} "
            f"{payload.get('target_type')}:{payload.get('target_id')}"
        )

    @staticmethod
    def _run_detail(payload: dict) -> str:
        return f"Run {payload.get('id')} started for task {payload.get('task_id')}."

    @staticmethod
    def _run_completion_detail(payload: dict) -> str:
        return f"Run {payload.get('id')} completed with status {payload.get('status', 'unknown')}."

    @staticmethod
    def _run_update_detail(payload: dict) -> str:
        metadata = payload.get("metadata", {})
        if not metadata:
            return f"Run {payload.get('id')} metadata updated."
        keys = ", ".join(sorted(metadata.keys()))
        return f"Run {payload.get('id')} metadata updated: {keys}."

    @staticmethod
    def _candidate_detail(payload: dict) -> str:
        kind = payload.get("kind", "unknown")
        action = payload.get("action", "accepted")
        reason_code = payload.get("reason_code", "unspecified")
        trigger_source = payload.get("trigger_source", "system")
        return f"Accepted {kind} candidate with action {action} ({reason_code} via {trigger_source})."

    @staticmethod
    def _candidate_defer_detail(payload: dict) -> str:
        due_hint = payload.get("due_hint", "later")
        reason_code = payload.get("reason_code", "unspecified")
        return f"Deferred candidate until {due_hint} ({reason_code})."

    @staticmethod
    def _candidate_batch_detail(payload: dict) -> str:
        skip_counts = EventQueryService._skip_reason_summary(payload)
        return (
            f"Accepted {payload.get('accepted_count', 0)}, "
            f"skipped {payload.get('skipped_count', 0)}, "
            f"errors {payload.get('error_count', 0)}"
            + (f", skip reasons: {skip_counts}." if skip_counts else ".")
        )

    @staticmethod
    def _scheduler_tick_detail(payload: dict) -> str:
        skip_counts = EventQueryService._skip_reason_summary(payload)
        return (
            f"Discovered {payload.get('discovered_count', 0)}, "
            f"auto-accepted {payload.get('auto_accepted_count', 0)}, "
            f"auto-started {payload.get('auto_started_count', 0)}, "
            f"auto-verified {payload.get('auto_verified_count', 0)}, "
            f"blocked follow-ups {payload.get('blocked_followup_count', 0)}, "
            f"stalled reminders {payload.get('stalled_reminder_count', 0)}, "
            f"escalations {payload.get('escalated_count', 0)}, "
            f"skipped {payload.get('skipped_count', 0)}, "
            f"errors {payload.get('error_count', 0)}"
            + (f", skip reasons: {skip_counts}." if skip_counts else ".")
        )

    @staticmethod
    def _skip_reason_summary(payload: dict) -> str:
        skip_reason_counts = payload.get("skip_reason_counts", {})
        if not skip_reason_counts:
            return ""
        return ", ".join(
            f"{reason}={count}" for reason, count in sorted(skip_reason_counts.items())
        )

    @staticmethod
    def _stalled_task_detail(payload: dict) -> str:
        return f"Created reminder for stalled task {payload.get('task_id')} after {payload.get('stale_after_minutes', 'unknown')} minutes."

    @staticmethod
    def _stalled_followup_detail(payload: dict) -> str:
        return (
            f"Created follow-up {payload.get('followup_task_id')} for blocked task "
            f"{payload.get('task_id')} after {payload.get('stale_after_minutes', 'unknown')} minutes."
        )

    @staticmethod
    def _stalled_escalation_detail(payload: dict) -> str:
        actions = ", ".join(payload.get("actions", [])) or "no actions recorded"
        return (
            f"Escalated stalled task {payload.get('task_id')} via {payload.get('policy_name', 'default_policy')} "
            f"after {payload.get('escalate_after_hits', 'unknown')} hits: {actions}."
        )

    @staticmethod
    def _reminder_resume_detail(payload: dict) -> str:
        action = payload.get("action", "resumed_existing_task")
        reminder_id = payload.get("reminder_id", "unknown")
        return f"Reminder {reminder_id} resumed task via {action}."
