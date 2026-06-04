from __future__ import annotations

from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, LabeledPrice, Message

from .config import Config
from .content import ContentStore
from .database import Database
from .keyboards import test_payment_keyboard


class PaymentService:
    def __init__(self, config: Config, content: ContentStore, db: Database) -> None:
        self.config = config
        self.content = content
        self.db = db

    async def start_payment(self, message: Message, user_id: int, product_id: str) -> str:
        amount = self.db.price(product_id)
        order_id = self.db.create_order(user_id, product_id, amount, self.config.payment_mode)
        product_title = self.content.product_title(product_id)

        if self.config.payment_mode == "test":
            if not self.config.enable_test_payments:
                await message.answer("Тестовая оплата отключена. Попросите администратора настроить платежный режим.")
                return order_id
            await message.answer(
                f"Заказ {order_id}\n"
                f"Товар: {product_title}\n"
                f"Сумма: {amount} руб.\n\n"
                "Это тестовый режим. Нажмите кнопку, чтобы имитировать успешную оплату.",
                reply_markup=test_payment_keyboard(order_id),
            )
            return order_id

        if self.config.payment_mode in {"manual", "yoomoney"}:
            details = self._manual_details()
            await message.answer(
                f"Заказ {order_id}\n"
                f"Товар: {product_title}\n"
                f"Сумма: {amount} руб.\n\n"
                f"Оплатите по реквизитам:\n{details}\n\n"
                "После оплаты отправьте чек или сообщение об оплате прямо сюда. Администратор подтвердит заказ командой "
                f"/admin_confirm {order_id}, и бот выдаст материалы."
            )
            return order_id

        if self.config.payment_mode == "telegram":
            if not self.config.telegram_provider_token:
                await message.answer("Telegram Payments не настроен: отсутствует TELEGRAM_PROVIDER_TOKEN.")
                return order_id
            await message.bot.send_invoice(
                chat_id=user_id,
                title=product_title,
                description=self.content.product(product_id)["positioning"][:255],
                payload=order_id,
                provider_token=self.config.telegram_provider_token,
                currency=self.config.payment_currency,
                prices=[LabeledPrice(label=product_title, amount=amount * 100)],
            )
            return order_id

        await message.answer("Неизвестный платежный режим. Проверьте PAYMENT_MODE.")
        return order_id

    async def confirm_and_deliver(self, bot: Bot, order_id: str, payload: str | None = None) -> str:
        order = self.db.get_order(order_id)
        if order is None:
            return f"Заказ {order_id} не найден."
        if order["status"] != "paid":
            order = self.db.mark_order_paid(order_id, payload)
        return await self.deliver(bot, int(order["user_id"]), str(order["product_id"]), order_id)

    async def deliver(self, bot: Bot, user_id: int, product_id: str, order_id: str) -> str:
        if product_id not in self.config.product_files:
            return await self._deliver_inside_bot_product(bot, user_id, product_id, order_id)

        files = self.config.product_files[product_id]
        missing = [path for path in files if not path.exists()]
        if missing:
            missing_text = "\n".join(str(path) for path in missing)
            await bot.send_message(
                user_id,
                "Оплата подтверждена, но файл для выдачи не найден. "
                "Администратор должен проверить пути к книгам.\n\n"
                f"Не найдены:\n{missing_text}",
            )
            return f"Оплата подтверждена, но не найдены файлы:\n{missing_text}"

        title = self.content.product_title(product_id)
        await bot.send_message(user_id, f"Оплата подтверждена. Отправляю материалы: {title}.")
        for path in files:
            await bot.send_document(
                user_id,
                FSInputFile(path),
                caption=_caption_for_file(path),
            )
        self.db.add_purchase(user_id, product_id, order_id)
        await bot.send_message(
            user_id,
            "Спасибо за покупку. Если книга попадет в состояние, поделитесь ботом с тем, кому это тоже может быть нужно.",
        )
        return f"Заказ {order_id} оплачен и выдан пользователю {user_id}."

    def _manual_details(self) -> str:
        if self.config.payment_mode == "yoomoney":
            parts = [self.config.payment_provider_name or "ЮMoney"]
            if self.config.yoomoney_card_number:
                parts.append(f"Карта для перевода: {self.config.yoomoney_card_number}")
            if self.config.manual_payment_details:
                parts.append(self.config.manual_payment_details)
            return "\n".join(parts)
        return self.config.manual_payment_details or "Реквизиты пока не указаны администратором."

    async def _deliver_inside_bot_product(self, bot: Bot, user_id: int, product_id: str, order_id: str) -> str:
        product = self.content.product(product_id)
        title = product["title"]
        await bot.send_message(user_id, f"Оплата подтверждена. Открываю внутриботовый продукт: {title}.")
        await bot.send_message(user_id, product["positioning"])
        if product_id == "deep_reading":
            await bot.send_message(user_id, "Чтобы получить разбор, отправьте команду /deep и одним сообщением опишите ситуацию.")
        elif product_id == "mini_course_plus":
            await bot.send_message(user_id, "Мини-курс доступен внутри бота. Нажмите «Мини-курс» в меню или используйте /course.")
        elif product_id in {"book1_plus_reading", "book2_plus_reading", "bundle_bonus"}:
            base_product = "book1" if product_id == "book1_plus_reading" else "book2"
            if product_id == "bundle_bonus":
                base_product = "bundle"
            await self.deliver(bot, user_id, base_product, order_id)
            await bot.send_message(user_id, "Бонус открыт: используйте /plan для персонального плана чтения и /course для мини-курса.")
        self.db.add_purchase(user_id, product_id, order_id)
        return f"Заказ {order_id} оплачен и выдан пользователю {user_id}."


def _caption_for_file(path: Path) -> str:
    return path.name
