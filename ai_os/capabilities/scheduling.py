from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from ai_os.domain import (
    CalendarEventRecord,
    CapabilityDescriptor,
    CapabilityExecutionPayload,
    CapabilityExecutionResult,
    ReminderRecord,
    RiskLevel,
    utc_now,
)


class RemindersCapability:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.store_path = self.workspace_root / ".ai_os" / "reminders.json"
        self.descriptor = CapabilityDescriptor(
            name="reminders",
            description="Create and inspect local reminder entries stored inside the workspace.",
            risk_level=RiskLevel.LOW,
            scopes=["reminders:create", "reminders:list", "reminders:reschedule"],
            device_affinity=["mac_local", "ios_remote"],
            evidence_outputs=["Reminder scheduled"],
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        reminders = self._load()
        if payload.action == "create":
            due_hint = str(payload.parameters.get("due_hint", "unspecified"))
            reminder = ReminderRecord(
                id=str(uuid4()),
                title=str(payload.parameters.get("title", "Untitled reminder")),
                note=str(payload.parameters.get("note", "")),
                due_hint=due_hint,
                scheduled_for=self._resolve_schedule(
                    due_hint=due_hint,
                    explicit_scheduled_for=payload.parameters.get("scheduled_for"),
                ),
                source_task_id=str(payload.parameters["source_task_id"]) if payload.parameters.get("source_task_id") else None,
                origin=str(payload.parameters["origin"]) if payload.parameters.get("origin") else None,
            )
            reminders.append(reminder)
            self._save(reminders)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps(reminder.model_dump(mode="json")),
            )
        if payload.action == "list":
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps([reminder.model_dump(mode="json") for reminder in reminders]),
            )
        if payload.action == "delete":
            reminder_id = str(payload.parameters.get("id", ""))
            filtered = [item for item in reminders if item.id != reminder_id]
            self._save(filtered)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Reminder removed: {reminder_id}",
            )
        if payload.action == "reschedule":
            reminder_id = str(payload.parameters.get("id", ""))
            due_hint = str(payload.parameters.get("due_hint", "rescheduled"))
            scheduled_for = self._resolve_schedule(
                due_hint=due_hint,
                explicit_scheduled_for=payload.parameters.get("scheduled_for"),
            )
            origin = str(payload.parameters["origin"]) if payload.parameters.get("origin") else None
            updated_count = 0
            updated: list[ReminderRecord] = []
            for reminder in reminders:
                if reminder.id == reminder_id:
                    update = {"due_hint": due_hint, "scheduled_for": scheduled_for, "last_seen_at": None}
                    if origin:
                        update["origin"] = origin
                    reminder = reminder.model_copy(update=update)
                    updated_count += 1
                updated.append(reminder)
            self._save(updated)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Reminder rescheduled: {reminder_id} ({updated_count})",
            )
        if payload.action == "mark_seen":
            reminder_id = str(payload.parameters.get("id", ""))
            marked_count = 0
            marked_at = self._parse_datetime(payload.parameters.get("seen_at")) or utc_now()
            updated: list[ReminderRecord] = []
            for reminder in reminders:
                if reminder.id == reminder_id:
                    reminder = reminder.model_copy(update={"last_seen_at": marked_at})
                    marked_count += 1
                updated.append(reminder)
            self._save(updated)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Reminder marked seen: {reminder_id} ({marked_count})",
            )
        raise ValueError(f"Unsupported reminders action: {payload.action}")

    def _load(self) -> list[ReminderRecord]:
        if not self.store_path.exists():
            return []
        raw_items = json.loads(self.store_path.read_text(encoding="utf-8"))
        return [ReminderRecord.model_validate(item) for item in raw_items]

    def _save(self, reminders: list[ReminderRecord]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [reminder.model_dump(mode="json") for reminder in reminders]
        self.store_path.write_text(json.dumps(serialized, ensure_ascii=True, indent=2), encoding="utf-8")

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        return datetime.fromisoformat(value)

    @classmethod
    def _resolve_schedule(cls, due_hint: str, explicit_scheduled_for: object) -> datetime:
        if parsed := cls._parse_datetime(explicit_scheduled_for):
            return parsed

        lowered = due_hint.lower()
        now = utc_now()
        if "later today" in lowered:
            return now + timedelta(hours=4)
        if "tomorrow" in lowered or "next review cycle" in lowered:
            return now + timedelta(days=1)
        if "next week" in lowered or "weekly" in lowered:
            return now + timedelta(days=7)
        return now


class CalendarCapability:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.store_path = self.workspace_root / ".ai_os" / "calendar_events.json"
        self.descriptor = CapabilityDescriptor(
            name="calendar",
            description="Create and inspect local calendar events stored inside the workspace.",
            risk_level=RiskLevel.MEDIUM,
            scopes=["calendar:create", "calendar:list", "calendar:reschedule", "calendar:delete", "calendar:mark_seen"],
            device_affinity=["mac_local", "ios_remote"],
            evidence_outputs=["Local calendar event scheduled"],
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        events = self._load()
        if payload.action == "create":
            scheduled_for = RemindersCapability._resolve_schedule(
                due_hint=str(payload.parameters.get("due_hint", "later today")),
                explicit_scheduled_for=payload.parameters.get("scheduled_for"),
            )
            event = CalendarEventRecord(
                id=str(uuid4()),
                title=str(payload.parameters.get("title", "Untitled event")),
                note=str(payload.parameters.get("note", "")),
                due_hint=str(payload.parameters.get("due_hint", "later today")),
                scheduled_for=scheduled_for,
                duration_minutes=int(payload.parameters.get("duration_minutes", 30)),
                source_task_id=str(payload.parameters["source_task_id"]) if payload.parameters.get("source_task_id") else None,
                origin=str(payload.parameters["origin"]) if payload.parameters.get("origin") else None,
            )
            events.append(event)
            self._save(events)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps(event.model_dump(mode="json")),
            )
        if payload.action == "list":
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=json.dumps([event.model_dump(mode="json") for event in events]),
            )
        if payload.action == "delete":
            event_id = str(payload.parameters.get("id", ""))
            filtered = [item for item in events if item.id != event_id]
            self._save(filtered)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Calendar event removed: {event_id}",
            )
        if payload.action == "reschedule":
            event_id = str(payload.parameters.get("id", ""))
            scheduled_for = RemindersCapability._resolve_schedule(
                due_hint=str(payload.parameters.get("due_hint", "later today")),
                explicit_scheduled_for=payload.parameters.get("scheduled_for"),
            )
            updated: list[CalendarEventRecord] = []
            count = 0
            for event in events:
                if event.id == event_id:
                    event = event.model_copy(
                        update={
                            "scheduled_for": scheduled_for,
                            "due_hint": str(payload.parameters.get("due_hint", event.due_hint)),
                            "last_seen_at": None,
                        }
                    )
                    count += 1
                updated.append(event)
            self._save(updated)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Calendar event rescheduled: {event_id} ({count})",
            )
        if payload.action == "mark_seen":
            event_id = str(payload.parameters.get("id", ""))
            seen_at = RemindersCapability._parse_datetime(payload.parameters.get("seen_at")) or utc_now()
            updated: list[CalendarEventRecord] = []
            count = 0
            for event in events:
                if event.id == event_id:
                    event = event.model_copy(update={"last_seen_at": seen_at})
                    count += 1
                updated.append(event)
            self._save(updated)
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="ok",
                output=f"Calendar event marked seen: {event_id} ({count})",
            )
        raise ValueError(f"Unsupported calendar action: {payload.action}")

    def _load(self) -> list[CalendarEventRecord]:
        if not self.store_path.exists():
            return []
        raw_items = json.loads(self.store_path.read_text(encoding="utf-8"))
        return [CalendarEventRecord.model_validate(item) for item in raw_items]

    def _save(self, events: list[CalendarEventRecord]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps([event.model_dump(mode="json") for event in events], ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
