from datetime import datetime

import aiosqlite
from aiogram.types import User

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT,
    full_name   TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL,
    service     TEXT NOT NULL,
    comment     TEXT,
    status      TEXT NOT NULL DEFAULT 'new',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leads_user ON leads(user_id);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База не подключена: вызовите connect()")
        return self._conn

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def upsert_user(self, user: User) -> None:
        await self.conn.execute(
            """
            INSERT INTO users (id, username, full_name, created_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET username = excluded.username, full_name = excluded.full_name
            """,
            (user.id, user.username, user.full_name, _now()),
        )
        await self.conn.commit()

    async def create_lead(self, user_id: int, name: str, phone: str, service: str, comment: str | None) -> dict:
        now = _now()
        cursor = await self.conn.execute(
            """
            INSERT INTO leads (user_id, name, phone, service, comment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, phone, service, comment, now, now),
        )
        await self.conn.commit()
        return await self.get_lead(cursor.lastrowid)

    async def get_lead(self, lead_id: int) -> dict | None:
        async with self.conn.execute(
            """
            SELECT leads.*, users.username FROM leads
            JOIN users ON users.id = leads.user_id
            WHERE leads.id = ?
            """,
            (lead_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def set_status(self, lead_id: int, status: str) -> dict | None:
        await self.conn.execute(
            "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), lead_id),
        )
        await self.conn.commit()
        return await self.get_lead(lead_id)

    async def user_leads(self, user_id: int, limit: int = 10) -> list[dict]:
        async with self.conn.execute(
            "SELECT * FROM leads WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def all_leads(self) -> list[dict]:
        async with self.conn.execute(
            """
            SELECT leads.*, users.username FROM leads
            JOIN users ON users.id = leads.user_id
            ORDER BY leads.id
            """
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def all_user_ids(self) -> list[int]:
        async with self.conn.execute("SELECT id FROM users") as cursor:
            return [row["id"] for row in await cursor.fetchall()]

    async def stats(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        async with self.conn.execute("SELECT status, COUNT(*) AS n FROM leads GROUP BY status") as cursor:
            by_status = {row["status"]: row["n"] for row in await cursor.fetchall()}
        async with self.conn.execute(
            "SELECT COUNT(*) AS n FROM leads WHERE created_at LIKE ?", (f"{today}%",)
        ) as cursor:
            leads_today = (await cursor.fetchone())["n"]
        async with self.conn.execute("SELECT COUNT(*) AS n FROM users") as cursor:
            users = (await cursor.fetchone())["n"]
        return {
            "by_status": by_status,
            "total": sum(by_status.values()),
            "today": leads_today,
            "users": users,
        }
