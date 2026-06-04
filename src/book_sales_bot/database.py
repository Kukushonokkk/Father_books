from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def setup(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                marketing_opt_in INTEGER NOT NULL DEFAULT 0,
                current_quiz_step INTEGER NOT NULL DEFAULT 0,
                segment TEXT,
                readiness_score INTEGER NOT NULL DEFAULT 0,
                warmup_index INTEGER NOT NULL DEFAULT 0,
                next_warmup_at TEXT,
                blocked_at TEXT
            );

            CREATE TABLE IF NOT EXISTS user_tags (
                user_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                UNIQUE(user_id, tag)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                amount_rub INTEGER NOT NULL,
                status TEXT NOT NULL,
                payment_mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                provider_payload TEXT
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                delivered_at TEXT NOT NULL,
                UNIQUE(user_id, product_id, order_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS text_overrides (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                value TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                user_id INTEGER PRIMARY KEY,
                segment TEXT NOT NULL,
                pain TEXT NOT NULL,
                motivation TEXT NOT NULL,
                readiness_score INTEGER NOT NULL,
                recommended_product_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._ensure_column("users", "segment", "TEXT")
        self._ensure_column("users", "readiness_score", "INTEGER NOT NULL DEFAULT 0")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def seed_defaults(self, prices: dict[str, int]) -> None:
        for product_id, price in prices.items():
            key = f"price_{product_id}"
            if self.get_setting(key) is None:
                self.set_setting(key, str(price))

    def upsert_user(self, telegram_id: int, username: str | None, full_name: str | None) -> None:
        now = iso()
        self.conn.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                last_seen_at=excluded.last_seen_at,
                blocked_at=NULL
            """,
            (telegram_id, username, full_name, now, now),
        )
        self.conn.commit()

    def get_user(self, telegram_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()

    def set_opt_in(self, telegram_id: int, enabled: bool, next_at: datetime | None = None) -> None:
        self.conn.execute(
            "UPDATE users SET marketing_opt_in=?, next_warmup_at=? WHERE telegram_id=?",
            (1 if enabled else 0, iso(next_at) if next_at else None, telegram_id),
        )
        self.conn.commit()

    def set_quiz_step(self, telegram_id: int, step: int) -> None:
        self.conn.execute("UPDATE users SET current_quiz_step=? WHERE telegram_id=?", (step, telegram_id))
        self.conn.commit()

    def add_tag(self, telegram_id: int, tag: str) -> None:
        self.conn.execute("INSERT OR IGNORE INTO user_tags (user_id, tag) VALUES (?, ?)", (telegram_id, tag))
        self.conn.commit()

    def clear_tags(self, telegram_id: int) -> None:
        self.conn.execute("DELETE FROM user_tags WHERE user_id=?", (telegram_id,))
        self.conn.commit()

    def tags(self, telegram_id: int) -> list[str]:
        rows = self.conn.execute("SELECT tag FROM user_tags WHERE user_id=? ORDER BY tag", (telegram_id,))
        return [row["tag"] for row in rows.fetchall()]

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, iso()),
        )
        self.conn.commit()

    def price(self, product_id: str) -> int:
        value = self.get_setting(f"price_{product_id}")
        if value is None:
            raise KeyError(f"price for {product_id} is not configured")
        return int(value)

    def set_price(self, product_id: str, amount_rub: int) -> None:
        if amount_rub <= 0:
            raise ValueError("price must be positive")
        self.set_setting(f"price_{product_id}", str(amount_rub))

    def set_profile(
        self,
        user_id: int,
        segment: str,
        pain: str,
        motivation: str,
        readiness_score: int,
        recommended_product_id: str,
        summary: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO user_profile (
                user_id, segment, pain, motivation, readiness_score,
                recommended_product_id, summary, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                segment=excluded.segment,
                pain=excluded.pain,
                motivation=excluded.motivation,
                readiness_score=excluded.readiness_score,
                recommended_product_id=excluded.recommended_product_id,
                summary=excluded.summary,
                updated_at=excluded.updated_at
            """,
            (user_id, segment, pain, motivation, readiness_score, recommended_product_id, summary, iso()),
        )
        self.conn.execute(
            "UPDATE users SET segment=?, readiness_score=? WHERE telegram_id=?",
            (segment, readiness_score, user_id),
        )
        self.conn.commit()

    def get_profile(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM user_profile WHERE user_id=?", (user_id,)).fetchone()

    def create_order(self, user_id: int, product_id: str, amount_rub: int, payment_mode: str) -> str:
        order_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            """
            INSERT INTO orders (id, user_id, product_id, amount_rub, status, payment_mode, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (order_id, user_id, product_id, amount_rub, payment_mode, iso()),
        )
        self.conn.commit()
        return order_id

    def get_order(self, order_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()

    def mark_order_paid(self, order_id: str, payload: str | None = None) -> sqlite3.Row:
        self.conn.execute(
            "UPDATE orders SET status='paid', paid_at=?, provider_payload=COALESCE(?, provider_payload) WHERE id=?",
            (iso(), payload, order_id),
        )
        self.conn.commit()
        order = self.get_order(order_id)
        if order is None:
            raise KeyError(order_id)
        return order

    def add_purchase(self, user_id: int, product_id: str, order_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO purchases (user_id, product_id, order_id, delivered_at) VALUES (?, ?, ?, ?)",
            (user_id, product_id, order_id, iso()),
        )
        self.conn.commit()

    def user_purchases(self, user_id: int) -> list[str]:
        rows = self.conn.execute("SELECT product_id FROM purchases WHERE user_id=?", (user_id,))
        return [row["product_id"] for row in rows.fetchall()]

    def recent_orders(self, limit: int = 10) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return list(rows.fetchall())

    def pending_orders_for_user(self, user_id: int) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT * FROM orders WHERE user_id=? AND status='pending' ORDER BY created_at DESC",
            (user_id,),
        )
        return list(rows.fetchall())

    def recent_users(self, limit: int = 10) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT * FROM users ORDER BY last_seen_at DESC LIMIT ?",
            (limit,),
        )
        return list(rows.fetchall())

    def stats(self) -> dict[str, Any]:
        user_count = self.conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        optins = self.conn.execute("SELECT COUNT(*) AS c FROM users WHERE marketing_opt_in=1").fetchone()["c"]
        paid = self.conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='paid'").fetchone()["c"]
        revenue = self.conn.execute("SELECT COALESCE(SUM(amount_rub), 0) AS s FROM orders WHERE status='paid'").fetchone()["s"]
        pending = self.conn.execute("SELECT COUNT(*) AS c FROM orders WHERE status='pending'").fetchone()["c"]
        profiles = self.conn.execute("SELECT COUNT(*) AS c FROM user_profile").fetchone()["c"]
        return {
            "users": user_count,
            "optins": optins,
            "paid_orders": paid,
            "pending_orders": pending,
            "revenue_rub": revenue,
            "profiles": profiles,
        }

    def track_event(self, user_id: int | None, name: str, value: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO events (user_id, name, value, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, value, iso()),
        )
        self.conn.commit()

    def event_stats(self) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT name, COUNT(*) AS count
            FROM events
            GROUP BY name
            ORDER BY count DESC, name
            """
        )
        return list(rows.fetchall())

    def segment_stats(self) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT COALESCE(segment, 'unknown') AS segment, COUNT(*) AS count
            FROM users
            GROUP BY COALESCE(segment, 'unknown')
            ORDER BY count DESC
            """
        )
        return list(rows.fetchall())

    def opted_in_users(self) -> list[int]:
        rows = self.conn.execute("SELECT telegram_id FROM users WHERE marketing_opt_in=1 AND blocked_at IS NULL")
        return [int(row["telegram_id"]) for row in rows.fetchall()]

    def mark_blocked(self, telegram_id: int) -> None:
        self.conn.execute("UPDATE users SET blocked_at=?, marketing_opt_in=0 WHERE telegram_id=?", (iso(), telegram_id))
        self.conn.commit()

    def due_warmup_users(self, limit: int = 50) -> list[sqlite3.Row]:
        now = iso()
        rows = self.conn.execute(
            """
            SELECT * FROM users
            WHERE marketing_opt_in=1
              AND blocked_at IS NULL
              AND (next_warmup_at IS NULL OR next_warmup_at <= ?)
            ORDER BY COALESCE(next_warmup_at, first_seen_at)
            LIMIT ?
            """,
            (now, limit),
        )
        return list(rows.fetchall())

    def advance_warmup(self, telegram_id: int, next_index: int, interval_hours: int) -> None:
        next_at = utcnow() + timedelta(hours=interval_hours)
        self.conn.execute(
            "UPDATE users SET warmup_index=?, next_warmup_at=? WHERE telegram_id=?",
            (next_index, iso(next_at), telegram_id),
        )
        self.conn.commit()

    def set_text_override(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO text_overrides (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, iso()),
        )
        self.conn.commit()

    def text_overrides(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT key, value FROM text_overrides ORDER BY key")
        return {row["key"]: row["value"] for row in rows.fetchall()}
