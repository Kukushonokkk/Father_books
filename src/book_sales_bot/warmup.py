from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from .config import Config
from .content import ContentStore
from .database import Database
from .keyboards import catalog_keyboard


class WarmupService:
    def __init__(self, config: Config, content: ContentStore, db: Database) -> None:
        self.config = config
        self.content = content
        self.db = db

    async def send_due(self, bot: Bot, limit: int = 50) -> int:
        if not self.config.warmup_enabled:
            return 0
        sent = 0
        for user in self.db.due_warmup_users(limit=limit):
            warmups = self.content.segment_warmups(user["segment"])
            index = int(user["warmup_index"])
            if index >= len(warmups):
                continue
            await self._send_warmup(bot, int(user["telegram_id"]), warmups[index])
            self.db.track_event(int(user["telegram_id"]), "warmup_sent", warmups[index].get("key"))
            self.db.advance_warmup(int(user["telegram_id"]), index + 1, self.config.warmup_interval_hours)
            sent += 1
        return sent

    async def send_next_for_all(self, bot: Bot) -> int:
        sent = 0
        for user_id in self.db.opted_in_users():
            user = self.db.get_user(user_id)
            if user is None:
                continue
            warmups = self.content.segment_warmups(user["segment"])
            index = min(int(user["warmup_index"]), len(warmups) - 1)
            if index < 0:
                continue
            await self._send_warmup(bot, user_id, warmups[index])
            self.db.track_event(user_id, "warmup_sent", warmups[index].get("key"))
            self.db.advance_warmup(user_id, min(index + 1, len(warmups)), self.config.warmup_interval_hours)
            sent += 1
        return sent

    async def broadcast(self, bot: Bot, text: str) -> tuple[int, int]:
        sent = 0
        failed = 0
        delay = 60 / max(self.config.max_broadcast_per_minute, 1)
        for user_id in self.db.opted_in_users():
            try:
                await bot.send_message(user_id, text, reply_markup=catalog_keyboard())
                self.db.track_event(user_id, "broadcast_sent")
                sent += 1
            except TelegramForbiddenError:
                self.db.mark_blocked(user_id)
                failed += 1
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
                failed += 1
            await asyncio.sleep(delay)
        return sent, failed

    async def _send_warmup(self, bot: Bot, user_id: int, warmup: dict[str, str]) -> None:
        overrides = self.db.text_overrides()
        key = warmup.get("key", "")
        title = overrides.get(f"{key}.title", warmup["title"])
        body = overrides.get(key, warmup["body"])
        cta = overrides.get(f"{key}.cta", warmup["cta"])
        text = f"{title}\n\n{body}\n\n{cta}"
        try:
            await bot.send_message(user_id, text, reply_markup=catalog_keyboard())
        except TelegramForbiddenError:
            self.db.mark_blocked(user_id)
