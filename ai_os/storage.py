from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ai_os.domain import (
    DeviceRecord,
    EntityRelation,
    EventRecord,
    ExecutionRunRecord,
    GoalRecord,
    MemoryRecord,
    SelfProfile,
    TaskRecord,
)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def session(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS self_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    layer TEXT NOT NULL DEFAULT 'semantic',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'user',
                    confidence REAL NOT NULL DEFAULT 0.8,
                    freshness TEXT NOT NULL DEFAULT 'active',
                    related_goal_ids TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    success_criteria TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    status TEXT NOT NULL,
                    subtasks TEXT NOT NULL,
                    deadline TEXT,
                    risk_level TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    execution_plan TEXT NOT NULL,
                    rollback_plan TEXT,
                    blocker_reason TEXT,
                    linked_goal_ids TEXT NOT NULL DEFAULT '[]',
                    artifact_paths TEXT NOT NULL,
                    verification_notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS execution_runs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    metadata TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
            if "execution_mode" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'file_artifact'")
            if "tags" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
            if "execution_plan" not in columns:
                conn.execute(
                    "ALTER TABLE tasks ADD COLUMN execution_plan TEXT NOT NULL DEFAULT '{\"mode\":\"file_artifact\",\"steps\":[],\"confirmation_required\":false,\"expected_evidence\":[]}'"
                )
            if "artifact_paths" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN artifact_paths TEXT NOT NULL DEFAULT '[]'")
            if "verification_notes" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN verification_notes TEXT NOT NULL DEFAULT '[]'")
            if "linked_goal_ids" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN linked_goal_ids TEXT NOT NULL DEFAULT '[]'")

            memory_columns = {row["name"] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
            if "layer" not in memory_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN layer TEXT NOT NULL DEFAULT 'semantic'")
            if "source" not in memory_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'user'")
            if "confidence" not in memory_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN confidence REAL NOT NULL DEFAULT 0.8")
            if "freshness" not in memory_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN freshness TEXT NOT NULL DEFAULT 'active'")
            if "related_goal_ids" not in memory_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN related_goal_ids TEXT NOT NULL DEFAULT '[]'")


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
                    id, objective, tags, success_criteria, owner, status, subtasks, deadline,
                    risk_level, execution_mode, execution_plan, rollback_plan, blocker_reason, linked_goal_ids, artifact_paths, verification_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.objective,
                    json.dumps(task.tags),
                    json.dumps(task.success_criteria),
                    task.owner,
                    task.status.value,
                    json.dumps(task.subtasks),
                    task.deadline.isoformat() if task.deadline else None,
                    task.risk_level.value,
                    task.execution_mode.value,
                    task.execution_plan.model_dump_json(),
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
                SET objective = ?, tags = ?, success_criteria = ?, owner = ?, status = ?, subtasks = ?,
                    deadline = ?, risk_level = ?, execution_mode = ?, execution_plan = ?, rollback_plan = ?, blocker_reason = ?, linked_goal_ids = ?, artifact_paths = ?, verification_notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    task.objective,
                    json.dumps(task.tags),
                    json.dumps(task.success_criteria),
                    task.owner,
                    task.status.value,
                    json.dumps(task.subtasks),
                    task.deadline.isoformat() if task.deadline else None,
                    task.risk_level.value,
                    task.execution_mode.value,
                    task.execution_plan.model_dump_json(),
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
            success_criteria=json.loads(row["success_criteria"]),
            owner=row["owner"],
            status=row["status"],
            subtasks=json.loads(row["subtasks"]),
            deadline=row["deadline"],
            risk_level=row["risk_level"],
            execution_mode=row["execution_mode"],
            execution_plan=json.loads(row["execution_plan"]),
            rollback_plan=row["rollback_plan"],
            blocker_reason=row["blocker_reason"],
            linked_goal_ids=json.loads(row["linked_goal_ids"]) if row["linked_goal_ids"] else [],
            artifact_paths=json.loads(row["artifact_paths"]),
            verification_notes=json.loads(row["verification_notes"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, event_type: str, payload: dict) -> None:
        with self.db.session() as conn:
            conn.execute(
                "INSERT INTO events (event_type, payload) VALUES (?, ?)",
                (event_type, json.dumps(payload)),
            )

    def list_recent(self, limit: int = 100) -> list[EventRecord]:
        with self.db.session() as conn:
            rows = conn.execute(
                "SELECT id, event_type, payload, created_at FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def list_for_task(self, task_id: str, limit: int = 100) -> list[EventRecord]:
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, payload, created_at
                FROM events
                WHERE json_extract(payload, '$.task_id') = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (task_id, limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def list_for_execution_run(self, run_id: str, limit: int = 100) -> list[EventRecord]:
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, payload, created_at
                FROM events
                WHERE json_extract(payload, '$.execution_run_id') = ?
                   OR json_extract(payload, '$.id') = ?
                   OR json_extract(payload, '$.source_type') = 'execution_run' AND json_extract(payload, '$.source_id') = ?
                   OR json_extract(payload, '$.target_type') = 'execution_run' AND json_extract(payload, '$.target_id') = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (run_id, run_id, run_id, run_id, limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EventRecord:
        return EventRecord(
            id=row["id"],
            event_type=row["event_type"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
        )


class RelationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, relation: EntityRelation) -> EntityRelation:
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO relations (
                    id, source_type, source_id, relation_type, target_type, target_id, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation.id,
                    relation.source_type,
                    relation.source_id,
                    relation.relation_type,
                    relation.target_type,
                    relation.target_id,
                    json.dumps(relation.metadata),
                    relation.created_at.isoformat(),
                ),
            )
        return relation

    def list_for_entity(self, entity_type: str, entity_id: str, limit: int = 100) -> list[EntityRelation]:
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM relations
                WHERE (source_type = ? AND source_id = ?)
                   OR (target_type = ? AND target_id = ?)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (entity_type, entity_id, entity_type, entity_id, limit),
            ).fetchall()
        return [self._row_to_relation(row) for row in rows]

    @staticmethod
    def _row_to_relation(row: sqlite3.Row) -> EntityRelation:
        return EntityRelation(
            id=row["id"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            relation_type=row["relation_type"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
        )


class ExecutionRunRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, run: ExecutionRunRecord) -> ExecutionRunRecord:
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO execution_runs (id, task_id, status, started_at, completed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.task_id,
                    run.status,
                    run.started_at.isoformat(),
                    run.completed_at.isoformat() if run.completed_at else None,
                    json.dumps(run.metadata),
                ),
            )
        return run

    def update(self, run: ExecutionRunRecord) -> ExecutionRunRecord:
        with self.db.session() as conn:
            conn.execute(
                """
                UPDATE execution_runs
                SET status = ?, completed_at = ?, metadata = ?
                WHERE id = ?
                """,
                (
                    run.status,
                    run.completed_at.isoformat() if run.completed_at else None,
                    json.dumps(run.metadata),
                    run.id,
                ),
            )
        return run

    def get(self, run_id: str) -> ExecutionRunRecord | None:
        with self.db.session() as conn:
            row = conn.execute("SELECT * FROM execution_runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def latest_for_task(self, task_id: str) -> ExecutionRunRecord | None:
        with self.db.session() as conn:
            row = conn.execute(
                """
                SELECT * FROM execution_runs
                WHERE task_id = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (task_id,),
            ).fetchone()
        return self._row_to_run(row) if row else None

    def list_for_task(self, task_id: str, limit: int = 100) -> list[ExecutionRunRecord]:
        with self.db.session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM execution_runs
                WHERE task_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (task_id, limit),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> ExecutionRunRecord:
        return ExecutionRunRecord(
            id=row["id"],
            task_id=row["task_id"],
            status=row["status"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            metadata=json.loads(row["metadata"]),
        )


class GoalRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, goal: GoalRecord) -> GoalRecord:
        with self.db.session() as conn:
            conn.execute("INSERT INTO goals (id, payload) VALUES (?, ?)", (goal.id, goal.model_dump_json()))
        return goal

    def list(self) -> list[GoalRecord]:
        with self.db.session() as conn:
            rows = conn.execute("SELECT payload FROM goals ORDER BY id DESC").fetchall()
        return [GoalRecord.model_validate_json(row["payload"]) for row in rows]

    def get(self, goal_id: str) -> GoalRecord | None:
        with self.db.session() as conn:
            row = conn.execute("SELECT payload FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return GoalRecord.model_validate_json(row["payload"]) if row else None

    def update(self, goal: GoalRecord) -> GoalRecord:
        with self.db.session() as conn:
            conn.execute("UPDATE goals SET payload = ? WHERE id = ?", (goal.model_dump_json(), goal.id))
        return goal


class DeviceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, device: DeviceRecord) -> DeviceRecord:
        with self.db.session() as conn:
            conn.execute(
                """
                INSERT INTO devices (id, payload) VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (device.id, device.model_dump_json()),
            )
        return device

    def list(self) -> list[DeviceRecord]:
        with self.db.session() as conn:
            rows = conn.execute("SELECT payload FROM devices ORDER BY id ASC").fetchall()
        return [DeviceRecord.model_validate_json(row["payload"]) for row in rows]

    def get(self, device_id: str) -> DeviceRecord | None:
        with self.db.session() as conn:
            row = conn.execute("SELECT payload FROM devices WHERE id = ?", (device_id,)).fetchone()
        return DeviceRecord.model_validate_json(row["payload"]) if row else None
