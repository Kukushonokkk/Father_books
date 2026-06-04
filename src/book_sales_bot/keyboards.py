from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Диагностика и подбор", callback_data="menu:quiz")],
            [InlineKeyboardButton(text="Каталог и цены", callback_data="menu:catalog")],
            [InlineKeyboardButton(text="Услуги внутри бота", callback_data="menu:services")],
            [InlineKeyboardButton(text="Бесплатный гид", callback_data="menu:lead")],
            [InlineKeyboardButton(text="Мини-курс", callback_data="course:quiet_water:0")],
            [InlineKeyboardButton(text="Задать вопрос", callback_data="menu:ask")],
            [InlineKeyboardButton(text="Получать прогрев", callback_data="consent:yes")],
            [InlineKeyboardButton(text="Поделиться ботом", callback_data="menu:share")],
        ]
    )


def consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, присылать материалы", callback_data="consent:yes")],
            [InlineKeyboardButton(text="Нет, только покупка", callback_data="consent:no")],
        ]
    )


def catalog_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ведьма чёрной воды", callback_data="product:book1")],
            [InlineKeyboardButton(text="Сборник рассказов", callback_data="product:book2")],
            [InlineKeyboardButton(text="Комплект из двух книг", callback_data="product:bundle")],
            [InlineKeyboardButton(text="Комплект + бонусы", callback_data="product:bundle_bonus")],
            [InlineKeyboardButton(text="Подобрать по ответам", callback_data="menu:quiz")],
            [InlineKeyboardButton(text="Главное меню", callback_data="menu:main")],
        ]
    )


def product_keyboard(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Купить", callback_data=f"buy:{product_id}")],
            [InlineKeyboardButton(text="Задать вопрос", callback_data="menu:ask")],
            [InlineKeyboardButton(text="Назад в каталог", callback_data="menu:catalog")],
            [InlineKeyboardButton(text="Главное меню", callback_data="menu:main")],
        ]
    )


def recommendation_keyboard(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть рекомендацию", callback_data=f"product:{product_id}")],
            [InlineKeyboardButton(text="Купить сейчас", callback_data=f"buy:{product_id}")],
            [InlineKeyboardButton(text="Сравнить все варианты", callback_data="menu:catalog")],
            [InlineKeyboardButton(text="Получить бесплатный гид", callback_data="menu:lead")],
        ]
    )


def quiz_keyboard(step: int, options: list[dict[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=option["label"], callback_data=f"quiz:{step}:{option['tag']}")]
            for option in options
        ]
    )


def test_payment_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Тестовая оплата", callback_data=f"test_pay:{order_id}")],
            [InlineKeyboardButton(text="Назад в каталог", callback_data="menu:catalog")],
        ]
    )


def services_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ИИ-разбор ситуации", callback_data="product:deep_reading")],
            [InlineKeyboardButton(text="Книга 1 + разбор", callback_data="product:book1_plus_reading")],
            [InlineKeyboardButton(text="Книга 2 + разбор", callback_data="product:book2_plus_reading")],
            [InlineKeyboardButton(text="Комплект + бонусы", callback_data="product:bundle_bonus")],
            [InlineKeyboardButton(text="Мини-курс", callback_data="product:mini_course_plus")],
            [InlineKeyboardButton(text="Главное меню", callback_data="menu:main")],
        ]
    )


def course_keyboard(course_id: str, lesson_index: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    if lesson_index + 1 < total:
        rows.append([InlineKeyboardButton(text="Следующий урок", callback_data=f"course:{course_id}:{lesson_index + 1}")])
    rows.append([InlineKeyboardButton(text="Каталог", callback_data="menu:catalog")])
    rows.append([InlineKeyboardButton(text="Главное меню", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
