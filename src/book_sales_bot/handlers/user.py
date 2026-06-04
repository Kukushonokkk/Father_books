from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery

from ..consultant import Consultant
from ..content import ContentStore
from ..database import Database, utcnow
from ..keyboards import (
    catalog_keyboard,
    consent_keyboard,
    course_keyboard,
    main_menu,
    product_keyboard,
    quiz_keyboard,
    recommendation_keyboard,
    services_keyboard,
)
from ..payments import PaymentService
from ..recommendations import recommend_by_tags
from ..segmentation import build_profile


def create_user_router(
    db: Database,
    content: ContentStore,
    consultant: Consultant,
    payments: PaymentService,
) -> Router:
    router = Router(name="user")

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        _touch_user(db, message)
        db.track_event(message.from_user.id, "start")
        welcome = _text(db, "welcome", content.funnel["welcome"])
        consent = _text(db, "consent", content.funnel["consent"])
        await message.answer(f"{welcome}\n\n{consent}", reply_markup=consent_keyboard())
        await message.answer(content.funnel["main_menu"], reply_markup=main_menu())

    @router.message(Command("stop"))
    async def stop(message: Message) -> None:
        _touch_user(db, message)
        db.track_event(message.from_user.id, "stop")
        db.set_opt_in(message.from_user.id, False)
        await message.answer("Рассылки и прогрев отключены. Покупки и консультации в боте остаются доступными.")

    @router.message(Command("catalog"))
    async def catalog(message: Message) -> None:
        _touch_user(db, message)
        db.track_event(message.from_user.id, "catalog_open")
        await message.answer(_catalog_text(db, content), reply_markup=catalog_keyboard())

    @router.message(Command("course"))
    async def course(message: Message) -> None:
        _touch_user(db, message)
        db.track_event(message.from_user.id, "course_open")
        await _send_course_lesson(message, content, "quiet_water", 0)

    @router.message(Command("plan"))
    async def plan(message: Message) -> None:
        _touch_user(db, message)
        db.track_event(message.from_user.id, "plan_request")
        await message.answer(_reading_plan(db, content, message.from_user.id), reply_markup=main_menu())

    @router.message(Command("deep"))
    async def deep(message: Message) -> None:
        _touch_user(db, message)
        db.track_event(message.from_user.id, "deep_request")
        allowed = {"deep_reading", "book1_plus_reading", "book2_plus_reading", "bundle_bonus"}
        purchases = set(db.user_purchases(message.from_user.id))
        if not purchases & allowed:
            await message.answer(
                "Глубокий ИИ-разбор доступен после покупки услуги или пакета с разбором.",
                reply_markup=product_keyboard("deep_reading"),
            )
            return
        question = (message.text or "").replace("/deep", "", 1).strip()
        if len(question) < 20:
            await message.answer("Опишите ситуацию после команды /deep одним сообщением: что происходит, что тревожит и какой выбор стоит перед вами.")
            return
        answer, product_id = await consultant.answer(message.from_user.id, question)
        await message.answer(f"Персональный разбор:\n\n{answer}", reply_markup=recommendation_keyboard(product_id))

    @router.message(Command("privacy"))
    async def privacy(message: Message) -> None:
        _touch_user(db, message)
        await message.answer(
            "Бот хранит минимальные данные: Telegram ID, имя, username, согласие на рассылку, интересы, заказы и покупки. "
            "Рассылки идут только после согласия. Команда /stop отключает прогрев."
        )

    @router.callback_query(F.data == "consent:yes")
    async def consent_yes(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "consent_yes")
        db.set_opt_in(callback.from_user.id, True, utcnow())
        await callback.answer("Согласие сохранено")
        await callback.message.answer(
            "Готово. Я буду присылать только смысловые материалы по книгам и редкие предложения. "
            "Отключить можно командой /stop.",
            reply_markup=main_menu(),
        )

    @router.callback_query(F.data == "consent:no")
    async def consent_no(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "consent_no")
        db.set_opt_in(callback.from_user.id, False)
        await callback.answer("Согласие не включено")
        await callback.message.answer("Хорошо. Можно пользоваться подбором, консультацией и покупкой без рассылок.", reply_markup=main_menu())

    @router.callback_query(F.data == "menu:quiz")
    async def quiz_start(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "diagnostic_start")
        db.clear_tags(callback.from_user.id)
        db.set_quiz_step(callback.from_user.id, 0)
        question = content.quiz_questions()[0]
        await callback.answer()
        await callback.message.answer(content.funnel["quiz"]["intro"])
        await callback.message.answer(question["text"], reply_markup=quiz_keyboard(0, question["options"]))

    @router.callback_query(F.data.startswith("quiz:"))
    async def quiz_step(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        _, step_raw, tag = callback.data.split(":", 2)
        step = int(step_raw)
        questions = content.quiz_questions()
        db.add_tag(callback.from_user.id, tag)
        db.track_event(callback.from_user.id, f"diagnostic_answer_{step}", tag)
        next_step = step + 1
        db.set_quiz_step(callback.from_user.id, next_step)
        await callback.answer()
        if next_step < len(questions):
            question = questions[next_step]
            await callback.message.answer(question["text"], reply_markup=quiz_keyboard(next_step, question["options"]))
            return

        tags = db.tags(callback.from_user.id)
        profile = build_profile(tags, db.user_purchases(callback.from_user.id))
        db.set_profile(
            callback.from_user.id,
            profile.segment,
            profile.pain,
            profile.motivation,
            profile.readiness_score,
            profile.recommended_product_id,
            profile.summary,
        )
        db.track_event(callback.from_user.id, "diagnostic_complete", profile.segment)
        rec = recommend_by_tags(tags, db.user_purchases(callback.from_user.id))
        await callback.message.answer(
            f"{profile.title}\n\n"
            f"Главная боль: {profile.pain}\n\n"
            f"Мотивация: {profile.motivation}\n\n"
            f"Готовность к покупке: {profile.readiness_score}/100\n\n"
            f"Рекомендация: {content.product_title(rec.product_id)}\n\n{rec.reason}",
            reply_markup=recommendation_keyboard(rec.product_id),
        )

    @router.callback_query(F.data == "menu:main")
    async def main_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "main_menu_open")
        await callback.answer()
        await callback.message.answer(content.funnel["main_menu"], reply_markup=main_menu())

    @router.callback_query(F.data == "menu:catalog")
    async def catalog_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "catalog_open")
        await callback.answer()
        await callback.message.answer(_catalog_text(db, content), reply_markup=catalog_keyboard())

    @router.callback_query(F.data == "menu:services")
    async def services_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "services_open")
        await callback.answer()
        await callback.message.answer(_services_text(content), reply_markup=services_keyboard())

    @router.callback_query(F.data == "menu:lead")
    async def lead_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "lead_magnet_open")
        await callback.answer()
        guide = content.lead_magnets["choice_guide"]
        await callback.message.answer(f"{guide['title']}\n\n{guide['body']}\n\n{guide['cta']}", reply_markup=main_menu())

    @router.callback_query(F.data.startswith("course:"))
    async def course_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        _, course_id, lesson_raw = callback.data.split(":", 2)
        lesson_index = int(lesson_raw)
        if lesson_index > 0 and not _course_unlocked(db, callback.from_user.id):
            db.track_event(callback.from_user.id, "course_locked", f"{course_id}:{lesson_raw}")
            await callback.answer()
            await callback.message.answer(
                "Первый урок открыт бесплатно. Полный мини-курс доступен после покупки мини-курса или комплекта с бонусами.",
                reply_markup=product_keyboard("mini_course_plus"),
            )
            return
        db.track_event(callback.from_user.id, "course_lesson", f"{course_id}:{lesson_raw}")
        await callback.answer()
        await _send_course_lesson(callback.message, content, course_id, lesson_index)

    @router.callback_query(F.data == "menu:share")
    async def share_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "share_open")
        await callback.answer()
        await callback.message.answer(content.funnel["share_text"])

    @router.callback_query(F.data == "menu:ask")
    async def ask_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        db.track_event(callback.from_user.id, "ask_prompt")
        await callback.answer()
        await callback.message.answer(
            "Напишите вопрос одним сообщением. Например: «Что выбрать, если мне близки мистика и тема одиночества?»"
        )

    @router.callback_query(F.data.startswith("product:"))
    async def product_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        product_id = callback.data.split(":", 1)[1]
        db.track_event(callback.from_user.id, "product_open", product_id)
        await callback.answer()
        await callback.message.answer(_product_text(db, content, product_id, callback.from_user.id), reply_markup=product_keyboard(product_id))

    @router.callback_query(F.data.startswith("buy:"))
    async def buy_callback(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        product_id = callback.data.split(":", 1)[1]
        db.track_event(callback.from_user.id, "buy_click", product_id)
        await callback.answer()
        await payments.start_payment(callback.message, callback.from_user.id, product_id)

    @router.callback_query(F.data.startswith("test_pay:"))
    async def test_pay(callback: CallbackQuery) -> None:
        _touch_callback_user(db, callback)
        order_id = callback.data.split(":", 1)[1]
        order = db.get_order(order_id)
        if order is None or int(order["user_id"]) != callback.from_user.id:
            await callback.answer("Заказ не найден", show_alert=True)
            return
        if str(order["payment_mode"]) != "test":
            await callback.answer("Это не тестовый заказ", show_alert=True)
            return
        await callback.answer("Оплата подтверждена")
        db.track_event(callback.from_user.id, "test_payment_confirmed", order_id)
        await payments.confirm_and_deliver(callback.bot, order_id, payload="test_payment")

    @router.pre_checkout_query()
    async def pre_checkout(query: PreCheckoutQuery) -> None:
        order = db.get_order(query.invoice_payload)
        if order is None:
            await query.answer(ok=False, error_message="Заказ не найден.")
            return
        if int(order["amount_rub"]) * 100 != query.total_amount:
            await query.answer(ok=False, error_message="Сумма заказа не совпадает.")
            return
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def successful_payment(message: Message) -> None:
        _touch_user(db, message)
        payment = message.successful_payment
        db.track_event(message.from_user.id, "telegram_payment_confirmed", payment.invoice_payload)
        await payments.confirm_and_deliver(message.bot, payment.invoice_payload, payload=str(payment))

    @router.message(F.photo | F.document)
    async def payment_receipt(message: Message) -> None:
        _touch_user(db, message)
        db.track_event(message.from_user.id, "receipt_sent")
        pending = db.pending_orders_for_user(message.from_user.id)
        order_text = "\n".join(f"{row['id']} | {row['product_id']} | {row['amount_rub']} руб." for row in pending) or "pending-заказы не найдены"
        await message.answer(
            "Получил файл/чек. Администратор проверит оплату и подтвердит заказ. "
            "Если заказов несколько, укажите номер заказа сообщением."
        )
        for admin_id in payments.config.admin_ids:
            await message.bot.send_message(
                admin_id,
                f"Пользователь {message.from_user.id} отправил чек.\nОжидающие заказы:\n{order_text}\n\n"
                "После проверки используйте /admin_confirm ORDER_ID.",
            )
            await message.copy_to(admin_id)

    @router.message(F.text)
    async def free_question(message: Message) -> None:
        _touch_user(db, message)
        if message.text and message.text.startswith("/"):
            await message.answer("Команда не распознана. Используйте /start, /catalog или задайте вопрос обычным текстом.")
            return
        if _looks_like_payment_message(message.text or "") and db.pending_orders_for_user(message.from_user.id):
            db.track_event(message.from_user.id, "payment_text_sent")
            await _notify_admins_about_payment_text(message, db, payments)
            await message.answer("Принял сообщение об оплате. Администратор проверит поступление и подтвердит заказ.")
            return
        db.track_event(message.from_user.id, "free_question")
        answer, product_id = await consultant.answer(message.from_user.id, message.text or "")
        await message.answer(answer, reply_markup=recommendation_keyboard(product_id))

    return router


def _touch_user(db: Database, message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    db.upsert_user(user.id, user.username, user.full_name)


def _touch_callback_user(db: Database, callback: CallbackQuery) -> None:
    user = callback.from_user
    db.upsert_user(user.id, user.username, user.full_name)


def _text(db: Database, key: str, default: str) -> str:
    return db.text_overrides().get(key, default)


def _catalog_text(db: Database, content: ContentStore) -> str:
    return (
        "Каталог:\n\n"
        f"1. {content.product_title('book1')} - {db.price('book1')} руб.\n"
        f"2. {content.product_title('book2')} - {db.price('book2')} руб.\n"
        f"3. {content.product_title('bundle')} - {db.price('bundle')} руб.\n\n"
        f"4. {content.product_title('bundle_bonus')} - {db.price('bundle_bonus')} руб.\n\n"
        f"Две книги по отдельности стоят {db.price('book1') + db.price('book2')} руб., комплект сейчас выгоднее."
    )


def _product_text(db: Database, content: ContentStore, product_id: str, user_id: int | None = None) -> str:
    product = content.product(product_id)
    price = db.price(product_id)
    offer = _ab_offer(db, content, product_id, user_id)
    offer_text = f"\n\n{offer}" if offer else ""
    return (
        f"{product['title']}\n\n"
        f"{product['positioning']}\n\n"
        f"{product['sales_pitch']}"
        f"{offer_text}\n\n"
        f"Цена: {price} руб."
    )


def _ab_offer(db: Database, content: ContentStore, product_id: str, user_id: int | None) -> str | None:
    override = db.text_overrides().get(f"offer_{product_id}")
    if override:
        return override
    offers = content.funnel.get("ab_offers", {}).get(product_id)
    if not offers:
        return None
    index = (user_id or 0) % len(offers)
    return offers[index]


def _services_text(content: ContentStore) -> str:
    lines = ["Услуги внутри бота:"]
    for service in content.services.values():
        lines.append(f"\n{service['title']}\nЦенность: {service['value']}\nСценарий: {service['scenario']}")
    return "\n".join(lines)


async def _send_course_lesson(message: Message, content: ContentStore, course_id: str, lesson_index: int) -> None:
    course = content.mini_courses[course_id]
    lessons = course["lessons"]
    lesson = lessons[lesson_index]
    await message.answer(
        f"{course['title']}\n\n"
        f"{lesson['title']}\n\n"
        f"{lesson['body']}\n\n"
        f"Практика: {lesson['practice']}\n\n"
        f"{lesson['cta']}",
        reply_markup=course_keyboard(course_id, lesson_index, len(lessons)),
    )


def _reading_plan(db: Database, content: ContentStore, user_id: int) -> str:
    purchases = set(db.user_purchases(user_id))
    if "bundle" in purchases or "bundle_bonus" in purchases:
        key = "bundle"
    elif "book1" in purchases or "book1_plus_reading" in purchases:
        key = "book1"
    elif "book2" in purchases or "book2_plus_reading" in purchases:
        key = "book2"
    else:
        return "План чтения открывается после покупки книги, комплекта или пакета. Пока можно пройти диагностику и получить бесплатный гид."
    steps = content.post_purchase["plans"][key]
    profile = db.get_profile(user_id)
    intro = content.post_purchase["plan_intro"]
    profile_text = f"\n\nВаш сегмент: {profile['segment']}." if profile else ""
    return intro + profile_text + "\n\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))


def _course_unlocked(db: Database, user_id: int) -> bool:
    purchases = set(db.user_purchases(user_id))
    return bool(purchases & {"mini_course_plus", "bundle_bonus"})


def _looks_like_payment_message(text: str) -> bool:
    normalized = text.lower()
    return any(word in normalized for word in ("оплатил", "оплатила", "оплата", "перевел", "перевела", "чек"))


async def _notify_admins_about_payment_text(message: Message, db: Database, payments: PaymentService) -> None:
    pending = db.pending_orders_for_user(message.from_user.id)
    order_text = "\n".join(f"{row['id']} | {row['product_id']} | {row['amount_rub']} руб." for row in pending)
    for admin_id in payments.config.admin_ids:
        await message.bot.send_message(
            admin_id,
            f"Пользователь {message.from_user.id} написал об оплате:\n{message.text}\n\n"
            f"Ожидающие заказы:\n{order_text}\n\n"
            "После проверки используйте /admin_confirm ORDER_ID.",
        )
