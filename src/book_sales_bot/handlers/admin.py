from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..config import Config
from ..content import ContentStore
from ..database import Database
from ..payments import PaymentService
from ..warmup import WarmupService


def create_admin_router(
    config: Config,
    db: Database,
    content: ContentStore,
    payments: PaymentService,
    warmup: WarmupService,
) -> Router:
    router = Router(name="admin")

    @router.message(Command("admin"))
    async def admin(message: Message) -> None:
        if not _is_admin(config, message):
            return
        stats = db.stats()
        await message.answer(
            "Админ-панель\n\n"
            f"Пользователи: {stats['users']}\n"
            f"Согласия на рассылку: {stats['optins']}\n"
            f"Оплаченные заказы: {stats['paid_orders']}\n"
            f"Ожидают оплаты: {stats['pending_orders']}\n"
            f"Диагностик завершено: {stats['profiles']}\n"
            f"Выручка: {stats['revenue_rub']} руб.\n\n"
            "Команды: /admin_prices, /admin_orders, /admin_users, /admin_stats, /admin_segments, "
            "/admin_offer, /admin_broadcast, /admin_warmup_now, /admin_texts"
        )

    @router.message(Command("admin_prices"))
    async def admin_prices(message: Message) -> None:
        if not _is_admin(config, message):
            return
        await message.answer(
            "Цены:\n"
            + "\n".join(f"{product_id}: {db.price(product_id)} руб." for product_id in content.product_ids())
            + "\n\n"
            "Изменить: /admin_set_price book1 1500"
        )

    @router.message(Command("admin_set_price"))
    async def admin_set_price(message: Message, command: CommandObject) -> None:
        if not _is_admin(config, message):
            return
        args = (command.args or "").split()
        if len(args) != 2:
            await message.answer("Формат: /admin_set_price book1 1500")
            return
        product_id, amount_raw = args
        if product_id not in content.product_ids():
            await message.answer("Неизвестный продукт. Используйте book1, book2 или bundle.")
            return
        try:
            amount = int(amount_raw)
            db.set_price(product_id, amount)
        except ValueError:
            await message.answer("Цена должна быть положительным числом.")
            return
        await message.answer(f"Цена {product_id} обновлена: {amount} руб.")

    @router.message(Command("admin_orders"))
    async def admin_orders(message: Message) -> None:
        if not _is_admin(config, message):
            return
        rows = db.recent_orders(limit=10)
        if not rows:
            await message.answer("Заказов пока нет.")
            return
        text = ["Последние заказы:"]
        for row in rows:
            text.append(
                f"{row['id']} | user {row['user_id']} | {row['product_id']} | "
                f"{row['amount_rub']} руб. | {row['status']} | {row['payment_mode']}"
            )
        await message.answer("\n".join(text))

    @router.message(Command("admin_stats"))
    async def admin_stats(message: Message) -> None:
        if not _is_admin(config, message):
            return
        rows = db.event_stats()
        if not rows:
            await message.answer("Событий пока нет.")
            return
        await message.answer("Аналитика событий:\n" + "\n".join(f"{row['name']}: {row['count']}" for row in rows))

    @router.message(Command("admin_segments"))
    async def admin_segments(message: Message) -> None:
        if not _is_admin(config, message):
            return
        rows = db.segment_stats()
        await message.answer("Сегменты:\n" + "\n".join(f"{row['segment']}: {row['count']}" for row in rows))

    @router.message(Command("admin_users"))
    async def admin_users(message: Message) -> None:
        if not _is_admin(config, message):
            return
        rows = db.recent_users(limit=10)
        if not rows:
            await message.answer("Пользователей пока нет.")
            return
        text = ["Последние пользователи:"]
        for row in rows:
            optin = "opt-in" if int(row["marketing_opt_in"]) else "no opt-in"
            text.append(f"{row['telegram_id']} | @{row['username'] or '-'} | {row['full_name'] or '-'} | {optin}")
        text.append("\nИзменить согласие вручную: /admin_set_optin USER_ID on")
        await message.answer("\n".join(text))

    @router.message(Command("admin_set_optin"))
    async def admin_set_optin(message: Message, command: CommandObject) -> None:
        if not _is_admin(config, message):
            return
        args = (command.args or "").split()
        if len(args) != 2:
            await message.answer("Формат: /admin_set_optin USER_ID on|off")
            return
        user_id_raw, mode = args
        try:
            user_id = int(user_id_raw)
        except ValueError:
            await message.answer("USER_ID должен быть числом.")
            return
        if db.get_user(user_id) is None:
            await message.answer("Пользователь не найден.")
            return
        if mode.lower() not in {"on", "off"}:
            await message.answer("Используйте on или off.")
            return
        db.set_opt_in(user_id, mode.lower() == "on")
        await message.answer(f"Согласие пользователя {user_id} установлено: {mode.lower()}.")

    @router.message(Command("admin_confirm"))
    async def admin_confirm(message: Message, command: CommandObject) -> None:
        if not _is_admin(config, message):
            return
        order_id = (command.args or "").strip()
        if not order_id:
            await message.answer("Формат: /admin_confirm ORDER_ID")
            return
        result = await payments.confirm_and_deliver(message.bot, order_id, payload="manual_admin_confirm")
        await message.answer(result)

    @router.message(Command("admin_broadcast"))
    async def admin_broadcast(message: Message, command: CommandObject) -> None:
        if not _is_admin(config, message):
            return
        text = (command.args or "").strip()
        if not text:
            await message.answer("Формат: /admin_broadcast текст сообщения")
            return
        sent, failed = await warmup.broadcast(message.bot, text)
        await message.answer(f"Рассылка завершена. Отправлено: {sent}, ошибок: {failed}.")

    @router.message(Command("admin_warmup_now"))
    async def admin_warmup_now(message: Message) -> None:
        if not _is_admin(config, message):
            return
        sent = await warmup.send_next_for_all(message.bot)
        await message.answer(f"Следующий прогрев отправлен пользователям с согласием: {sent}.")

    @router.message(Command("admin_texts"))
    async def admin_texts(message: Message) -> None:
        if not _is_admin(config, message):
            return
        overrides = db.text_overrides()
        if not overrides:
            await message.answer(
                "Переопределений нет.\n\n"
                "Примеры:\n"
                "/admin_text welcome Новый приветственный текст\n"
                "/admin_text consent Новый текст согласия\n"
                "/admin_text warmup_1 Новый текст первого прогрева"
            )
            return
        lines = ["Текстовые override:"]
        for key, value in overrides.items():
            lines.append(f"{key}: {value[:120]}")
        await message.answer("\n".join(lines))

    @router.message(Command("admin_text"))
    async def admin_text(message: Message, command: CommandObject) -> None:
        if not _is_admin(config, message):
            return
        args = (command.args or "").strip()
        if " " not in args:
            await message.answer("Формат: /admin_text key новый текст")
            return
        key, value = args.split(" ", 1)
        db.set_text_override(key.strip(), value.strip())
        await message.answer(f"Текст {key} обновлен.")

    @router.message(Command("admin_offer"))
    async def admin_offer(message: Message, command: CommandObject) -> None:
        if not _is_admin(config, message):
            return
        args = (command.args or "").strip()
        if " " not in args:
            await message.answer("Формат: /admin_offer product_id новый оффер")
            return
        product_id, value = args.split(" ", 1)
        if product_id not in content.product_ids():
            await message.answer("Неизвестный продукт.")
            return
        db.set_text_override(f"offer_{product_id}", value.strip())
        await message.answer(f"Оффер {product_id} обновлен.")

    return router


def _is_admin(config: Config, message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in config.admin_ids)
