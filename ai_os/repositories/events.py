from __future__ import annotations

import json
import sqlite3

from ai_os.domain import EntityRelation, EventRecord, ExecutionRunRecord

from .db import Database


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, event_type: str, payload: dict) -> None:
        with self.db.session() as conn:
            conn.execute("INSERT INTO events (event_type, payload) VALUES (?, ?)", (event_type, json.dumps(payload)))

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
