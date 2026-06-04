from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

from .config import load_config
from .consultant import Consultant
from .content import ContentStore
from .database import Database
from .handlers.admin import create_admin_router
from .handlers.user import create_user_router
from .payments import PaymentService
from .warmup import WarmupService


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = load_config()
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN is empty. Create .env from .env.example and fill BOT_TOKEN.")

    content = ContentStore.load(config.content_path)
    db = Database(config.database_path)
    db.setup()
    default_prices = content.default_prices()
    default_prices["book1"] = config.book_price_rub
    default_prices["book2"] = config.book_price_rub
    default_prices["bundle"] = config.bundle_price_rub
    db.seed_defaults(default_prices)

    consultant = Consultant(config, content, db)
    payments = PaymentService(config, content, db)
    warmup = WarmupService(config, content, db)

    session = AiohttpSession(
        proxy=config.telegram_proxy_url or None,
        timeout=config.telegram_request_timeout,
    )
    bot = Bot(token=config.bot_token, session=session)
    dp = Dispatcher()
    dp.include_router(create_admin_router(config, db, content, payments, warmup))
    dp.include_router(create_user_router(db, content, consultant, payments))

    warmup_task: asyncio.Task[None] | None = None

    async def on_startup() -> None:
        nonlocal warmup_task
        if config.warmup_enabled:
            warmup_task = asyncio.create_task(_warmup_loop(bot, warmup))

    async def on_shutdown() -> None:
        if warmup_task:
            warmup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await warmup_task

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except TelegramNetworkError as exc:
        logging.error(
            "Cannot connect to Telegram API. Check internet/VPN/proxy/firewall/DNS. "
            "If needed, set TELEGRAM_PROXY_URL in .env. Error: %s",
            exc,
        )
        raise
    finally:
        await bot.session.close()


async def _warmup_loop(bot: Bot, warmup: WarmupService) -> None:
    while True:
        try:
            await warmup.send_due(bot)
        except Exception:
            logging.exception("Warmup loop failed")
        await asyncio.sleep(60)


def cli() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    cli()
