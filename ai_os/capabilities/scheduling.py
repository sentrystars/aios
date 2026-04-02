from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
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


class AIOSLocalRemindersCapability:
    def __init__(self, workspace_root: Path, *, name: str = "aios_local_reminders") -> None:
        self.workspace_root = workspace_root.resolve()
        self.store_path = self.workspace_root / ".ai_os" / "reminders.json"
        self.descriptor = CapabilityDescriptor(
            name=name,
            description="Create and inspect reminder entries stored by AIOS inside the workspace.",
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


class AIOSLocalCalendarCapability:
    def __init__(self, workspace_root: Path, *, name: str = "aios_local_calendar") -> None:
        self.workspace_root = workspace_root.resolve()
        self.store_path = self.workspace_root / ".ai_os" / "calendar_events.json"
        self.descriptor = CapabilityDescriptor(
            name=name,
            description="Create and inspect calendar events stored by AIOS inside the workspace.",
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


class SystemRemindersCapability:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        platform: str | None = None,
        command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.enabled = enabled if enabled is not None else os.getenv("AIOS_ENABLE_SYSTEM_REMINDERS") == "1"
        self.platform = platform or sys.platform
        self.command_runner = command_runner or self._default_command_runner
        self.list_name = os.getenv("AIOS_SYSTEM_REMINDERS_LIST", "AIOS")
        self.descriptor = CapabilityDescriptor(
            name="system_reminders",
            description="Create and inspect reminders in the host system reminder service.",
            risk_level=RiskLevel.MEDIUM,
            scopes=["system_reminders:create", "system_reminders:list", "system_reminders:reschedule"],
            device_affinity=["mac_local", "ios_remote"],
            evidence_outputs=["System reminder scheduled"],
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        unavailable = self._unavailable_result(payload)
        if unavailable is not None:
            return unavailable
        if payload.action == "create":
            return self._create_reminder(payload)
        if payload.action == "list":
            return self._list_reminders(payload)
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="unsupported",
            output="System reminders bridge currently supports create and list only.",
        )

    def _unavailable_result(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult | None:
        if not self.enabled:
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="unavailable",
                output="System reminders bridge is disabled. Set AIOS_ENABLE_SYSTEM_REMINDERS=1 to enable it.",
            )
        if self.platform != "darwin":
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="unavailable",
                output="System reminders bridge is only available on macOS.",
            )
        return None

    def _create_reminder(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        title = str(payload.parameters.get("title", "Untitled reminder"))
        note = str(payload.parameters.get("note", ""))
        due_hint = str(payload.parameters.get("due_hint", "unspecified"))
        scheduled_for = RemindersCapability._resolve_schedule(
            due_hint=due_hint,
            explicit_scheduled_for=payload.parameters.get("scheduled_for"),
        )
        script = self._create_script(title=title, note=note, scheduled_for=scheduled_for)
        result = self.command_runner(script)
        if result.returncode != 0:
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="failed",
                output=(result.stderr or result.stdout or "Reminders bridge failed.").strip(),
            )
        reminder_id = (result.stdout or "").strip()
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="ok",
            output=json.dumps(
                {
                    "list_name": self.list_name,
                    "title": title,
                    "note": note,
                    "scheduled_for": scheduled_for.isoformat(),
                    "system_reminder_id": reminder_id,
                }
            ),
        )

    def _list_reminders(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        limit = int(payload.parameters.get("limit", 20))
        result = self.command_runner(self._list_script(limit=limit))
        if result.returncode != 0:
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="failed",
                output=(result.stderr or result.stdout or "Reminders bridge failed.").strip(),
            )
        lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
        items: list[dict[str, str]] = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            items.append(
                {
                    "system_reminder_id": parts[0],
                    "title": parts[1],
                    "due_date": parts[2],
                }
            )
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="ok",
            output=json.dumps(items),
        )

    def _create_script(self, *, title: str, note: str, scheduled_for: datetime) -> list[str]:
        month_name = scheduled_for.strftime("%B")
        return [
            'tell application "Reminders"',
            f'if not (exists list "{self._escape(self.list_name)}") then',
            f'    make new list with properties {{name:"{self._escape(self.list_name)}"}}',
            "end if",
            f'set targetList to list "{self._escape(self.list_name)}"',
            "set dueDate to (current date)",
            f"set year of dueDate to {scheduled_for.year}",
            f"set month of dueDate to {month_name}",
            f"set day of dueDate to {scheduled_for.day}",
            f"set time of dueDate to ({scheduled_for.hour} * hours) + ({scheduled_for.minute} * minutes)",
            (
                f'set newReminder to make new reminder at end of reminders of targetList with properties '
                f'{{name:"{self._escape(title)}", body:"{self._escape(note)}", due date:dueDate}}'
            ),
            "return id of newReminder",
            "end tell",
        ]

    def _list_script(self, *, limit: int) -> list[str]:
        return [
            'tell application "Reminders"',
            f'if not (exists list "{self._escape(self.list_name)}") then return ""',
            f'set targetList to list "{self._escape(self.list_name)}"',
            "set outputLines to {}",
            "set reminderCount to count of reminders of targetList",
            f"set maxCount to {limit}",
            "repeat with i from 1 to reminderCount",
            "    if i > maxCount then exit repeat",
            "    set itemRef to reminder i of targetList",
            '    set dueText to ""',
            "    try",
            "        set dueText to (due date of itemRef as text)",
            "    end try",
            '    set end of outputLines to ((id of itemRef as text) & tab & (name of itemRef as text) & tab & dueText)',
            "end repeat",
            "return outputLines as text",
            "end tell",
        ]

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _default_command_runner(script_lines: list[str]) -> subprocess.CompletedProcess[str]:
        command = ["osascript"]
        for line in script_lines:
            command.extend(["-e", line])
        return subprocess.run(command, capture_output=True, text=True, check=False)


class SystemCalendarCapability:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        platform: str | None = None,
        command_runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.enabled = enabled if enabled is not None else os.getenv("AIOS_ENABLE_SYSTEM_CALENDAR") == "1"
        self.platform = platform or sys.platform
        self.command_runner = command_runner or self._default_command_runner
        self.calendar_name = os.getenv("AIOS_SYSTEM_CALENDAR_NAME", "AIOS")
        self.descriptor = CapabilityDescriptor(
            name="system_calendar",
            description="Create and inspect events in the host system calendar service.",
            risk_level=RiskLevel.HIGH,
            confirmation_required=True,
            scopes=["system_calendar:create", "system_calendar:list", "system_calendar:reschedule", "system_calendar:delete"],
            device_affinity=["mac_local", "ios_remote"],
            evidence_outputs=["System calendar event scheduled"],
        )

    def execute(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        unavailable = self._unavailable_result(payload)
        if unavailable is not None:
            return unavailable
        if payload.action == "create":
            return self._create_event(payload)
        if payload.action == "list":
            return self._list_events(payload)
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="unsupported",
            output="System calendar bridge currently supports create and list only.",
            requires_confirmation=self.descriptor.confirmation_required,
        )

    def _unavailable_result(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult | None:
        if not self.enabled:
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="unavailable",
                output="System calendar bridge is disabled. Set AIOS_ENABLE_SYSTEM_CALENDAR=1 to enable it.",
                requires_confirmation=self.descriptor.confirmation_required,
            )
        if self.platform != "darwin":
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="unavailable",
                output="System calendar bridge is only available on macOS.",
                requires_confirmation=self.descriptor.confirmation_required,
            )
        return None

    def _create_event(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        title = str(payload.parameters.get("title", "Untitled event"))
        note = str(payload.parameters.get("note", ""))
        due_hint = str(payload.parameters.get("due_hint", "later today"))
        scheduled_for = RemindersCapability._resolve_schedule(
            due_hint=due_hint,
            explicit_scheduled_for=payload.parameters.get("scheduled_for"),
        )
        duration_minutes = int(payload.parameters.get("duration_minutes", 30))
        script = self._create_script(
            title=title,
            note=note,
            scheduled_for=scheduled_for,
            duration_minutes=duration_minutes,
        )
        result = self.command_runner(script)
        if result.returncode != 0:
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="failed",
                output=(result.stderr or result.stdout or "Calendar bridge failed.").strip(),
                requires_confirmation=self.descriptor.confirmation_required,
            )
        output = (result.stdout or "").strip()
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="ok",
            output=json.dumps(
                {
                    "calendar_name": self.calendar_name,
                    "title": title,
                    "note": note,
                    "scheduled_for": scheduled_for.isoformat(),
                    "duration_minutes": duration_minutes,
                    "system_event_uid": output,
                }
            ),
            requires_confirmation=self.descriptor.confirmation_required,
        )

    def _list_events(self, payload: CapabilityExecutionPayload) -> CapabilityExecutionResult:
        limit = int(payload.parameters.get("limit", 20))
        script = self._list_script(limit=limit)
        result = self.command_runner(script)
        if result.returncode != 0:
            return CapabilityExecutionResult(
                capability_name=self.descriptor.name,
                action=payload.action,
                status="failed",
                output=(result.stderr or result.stdout or "Calendar bridge failed.").strip(),
                requires_confirmation=self.descriptor.confirmation_required,
            )
        lines = [line for line in (result.stdout or "").splitlines() if line.strip()]
        items: list[dict[str, str]] = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            items.append(
                {
                    "system_event_uid": parts[0],
                    "title": parts[1],
                    "starts_at": parts[2],
                    "ends_at": parts[3],
                }
            )
        return CapabilityExecutionResult(
            capability_name=self.descriptor.name,
            action=payload.action,
            status="ok",
            output=json.dumps(items),
            requires_confirmation=self.descriptor.confirmation_required,
        )

    def _create_script(self, *, title: str, note: str, scheduled_for: datetime, duration_minutes: int) -> list[str]:
        month_name = scheduled_for.strftime("%B")
        return [
            'tell application "Calendar"',
            f'if not (exists calendar "{self._escape(self.calendar_name)}") then',
            f'    make new calendar with properties {{name:"{self._escape(self.calendar_name)}"}}',
            "end if",
            f'set targetCalendar to calendar "{self._escape(self.calendar_name)}"',
            "set startDate to (current date)",
            f"set year of startDate to {scheduled_for.year}",
            f"set month of startDate to {month_name}",
            f"set day of startDate to {scheduled_for.day}",
            f"set time of startDate to ({scheduled_for.hour} * hours) + ({scheduled_for.minute} * minutes)",
            f"set endDate to startDate + ({duration_minutes} * minutes)",
            (
                f'set newEvent to make new event at end of events of targetCalendar with properties '
                f'{{summary:"{self._escape(title)}", start date:startDate, end date:endDate, description:"{self._escape(note)}"}}'
            ),
            "return uid of newEvent",
            "end tell",
        ]

    def _list_script(self, *, limit: int) -> list[str]:
        return [
            'tell application "Calendar"',
            f'if not (exists calendar "{self._escape(self.calendar_name)}") then return ""',
            f'set targetCalendar to calendar "{self._escape(self.calendar_name)}"',
            "set outputLines to {}",
            "set eventCount to count of events of targetCalendar",
            f"set maxCount to {limit}",
            "repeat with i from 1 to eventCount",
            "    if i > maxCount then exit repeat",
            "    set evt to event i of targetCalendar",
            '    set end of outputLines to ((uid of evt as text) & tab & (summary of evt as text) & tab & (start date of evt as text) & tab & (end date of evt as text))',
            "end repeat",
            "return outputLines as text",
            "end tell",
        ]

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _default_command_runner(script_lines: list[str]) -> subprocess.CompletedProcess[str]:
        command = ["osascript"]
        for line in script_lines:
            command.extend(["-e", line])
        return subprocess.run(command, capture_output=True, text=True, check=False)


class RemindersCapability(AIOSLocalRemindersCapability):
    def __init__(self, workspace_root: Path) -> None:
        super().__init__(workspace_root, name="reminders")


class CalendarCapability(AIOSLocalCalendarCapability):
    def __init__(self, workspace_root: Path) -> None:
        super().__init__(workspace_root, name="calendar")
