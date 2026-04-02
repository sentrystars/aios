from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


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
                    intelligence_trace TEXT NOT NULL DEFAULT '{}',
                    success_criteria TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    status TEXT NOT NULL,
                    subtasks TEXT NOT NULL,
                    deadline TEXT,
                    risk_level TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    runtime_name TEXT,
                    execution_plan TEXT NOT NULL,
                    implementation_contract TEXT,
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
            if "runtime_name" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN runtime_name TEXT")
            if "tags" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
            if "intelligence_trace" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN intelligence_trace TEXT NOT NULL DEFAULT '{}'")
            if "execution_plan" not in columns:
                conn.execute(
                    "ALTER TABLE tasks ADD COLUMN execution_plan TEXT NOT NULL DEFAULT '{\"mode\":\"file_artifact\",\"steps\":[],\"confirmation_required\":false,\"expected_evidence\":[]}'"
                )
            if "implementation_contract" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN implementation_contract TEXT")
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
