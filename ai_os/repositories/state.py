from __future__ import annotations

import json
import sqlite3

from ai_os.domain import MemoryRecord, SelfProfile, TaskRecord

from .db import Database


class SelfRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def load(self) -> SelfProfile:
        with self.db.session() as conn:
            row = conn.execute("SELECT payload FROM self_profile WHERE id = 1").fetchone()
        if not row:
            return SelfProfile()
        return SelfProfile.model_validate_json(row["payload"])

    def save(self, profile: SelfProfile) -> SelfProfile:
        payload = profile.model_dump_json()
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO self_profile (id, payload) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (payload,),
            )
        return profile


class MemoryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, record: MemoryRecord) -> MemoryRecord:
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO memories (id, memory_type, layer, title, content, tags, source, confidence, freshness, related_goal_ids, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.memory_type.value,
                    record.layer.value,
                    record.title,
                    record.content,
                    json.dumps(record.tags),
                    record.source,
                    record.confidence,
                    record.freshness,
                    json.dumps(record.related_goal_ids),
                    record.created_at.isoformat(),
                ),
            )
        return record

    def list(self) -> list[MemoryRecord]:
        with self.db.session() as conn:
            rows = conn.execute(
                "SELECT id, memory_type, layer, title, content, tags, source, confidence, freshness, related_goal_ids, created_at FROM memories ORDER BY created_at DESC"
            ).fetchall()
        return [
            MemoryRecord(
                id=row["id"],
                memory_type=row["memory_type"],
                layer=row["layer"],
                title=row["title"],
                content=row["content"],
                tags=json.loads(row["tags"]),
                source=row["source"],
                confidence=row["confidence"],
                freshness=row["freshness"],
                related_goal_ids=json.loads(row["related_goal_ids"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]


class TaskRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, task: TaskRecord) -> TaskRecord:
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, objective, tags, intelligence_trace, success_criteria, owner, status, subtasks, deadline,
                    risk_level, execution_mode, runtime_name, execution_plan, implementation_contract, rollback_plan, blocker_reason, linked_goal_ids, artifact_paths, verification_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.objective,
                    json.dumps(task.tags),
                    json.dumps(task.intelligence_trace),
                    json.dumps(task.success_criteria),
                    task.owner,
                    task.status.value,
                    json.dumps(task.subtasks),
                    task.deadline.isoformat() if task.deadline else None,
                    task.risk_level.value,
                    task.execution_mode.value,
                    task.runtime_name,
                    task.execution_plan.model_dump_json(),
                    task.implementation_contract.model_dump_json() if task.implementation_contract else None,
                    task.rollback_plan,
                    task.blocker_reason,
                    json.dumps(task.linked_goal_ids),
                    json.dumps(task.artifact_paths),
                    json.dumps(task.verification_notes),
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                ),
            )
        return task

    def list(self) -> list[TaskRecord]:
        with self.db.session() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC").fetchall()
        return [self._row_to_task(row) for row in rows]

    def get(self, task_id: str) -> TaskRecord | None:
        with self.db.session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def update(self, task: TaskRecord) -> TaskRecord:
        with self.db.session() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET objective = ?, tags = ?, intelligence_trace = ?, success_criteria = ?, owner = ?, status = ?, subtasks = ?,
                    deadline = ?, risk_level = ?, execution_mode = ?, runtime_name = ?, execution_plan = ?, implementation_contract = ?, rollback_plan = ?, blocker_reason = ?, linked_goal_ids = ?, artifact_paths = ?, verification_notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    task.objective,
                    json.dumps(task.tags),
                    json.dumps(task.intelligence_trace),
                    json.dumps(task.success_criteria),
                    task.owner,
                    task.status.value,
                    json.dumps(task.subtasks),
                    task.deadline.isoformat() if task.deadline else None,
                    task.risk_level.value,
                    task.execution_mode.value,
                    task.runtime_name,
                    task.execution_plan.model_dump_json(),
                    task.implementation_contract.model_dump_json() if task.implementation_contract else None,
                    task.rollback_plan,
                    task.blocker_reason,
                    json.dumps(task.linked_goal_ids),
                    json.dumps(task.artifact_paths),
                    json.dumps(task.verification_notes),
                    task.updated_at.isoformat(),
                    task.id,
                ),
            )
        return task

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            objective=row["objective"],
            tags=json.loads(row["tags"]),
            intelligence_trace=json.loads(row["intelligence_trace"]) if row["intelligence_trace"] else {},
            success_criteria=json.loads(row["success_criteria"]),
            owner=row["owner"],
            status=row["status"],
            subtasks=json.loads(row["subtasks"]),
            deadline=row["deadline"],
            risk_level=row["risk_level"],
            execution_mode=row["execution_mode"],
            runtime_name=row["runtime_name"],
            execution_plan=json.loads(row["execution_plan"]),
            implementation_contract=json.loads(row["implementation_contract"]) if row["implementation_contract"] else None,
            rollback_plan=row["rollback_plan"],
            blocker_reason=row["blocker_reason"],
            linked_goal_ids=json.loads(row["linked_goal_ids"]) if row["linked_goal_ids"] else [],
            artifact_paths=json.loads(row["artifact_paths"]),
            verification_notes=json.loads(row["verification_notes"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
