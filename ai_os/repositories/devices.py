from __future__ import annotations

from ai_os.domain import DeviceRecord, GoalRecord

from .db import Database


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

    def get(self, device_id: str) -> DeviceRecord | None:
        with self.db.session() as conn:
            row = conn.execute("SELECT payload FROM devices WHERE id = ?", (device_id,)).fetchone()
        return DeviceRecord.model_validate_json(row["payload"]) if row else None

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
