from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProductView:
    product_id: str
    title: str
    short_title: str
    positioning: str
    sales_pitch: str


class ContentStore:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    @classmethod
    def load(cls, path: Path) -> "ContentStore":
        if path.exists():
            return cls(_repair_content(json.loads(path.read_text(encoding="utf-8"))))

        fallback = resources.files("book_sales_bot").joinpath("default_content.json")
        return cls(_repair_content(json.loads(fallback.read_text(encoding="utf-8"))))

    @property
    def products(self) -> dict[str, Any]:
        return self.data["products"]

    @property
    def funnel(self) -> dict[str, Any]:
        return self.data["funnel"]

    @property
    def strategy(self) -> dict[str, Any]:
        return self.data["strategy"]

    def product(self, product_id: str) -> dict[str, Any]:
        return self.products[product_id]

    def product_view(self, product_id: str) -> ProductView:
        product = self.product(product_id)
        return ProductView(
            product_id=product_id,
            title=product["title"],
            short_title=product.get("short_title", product["title"]),
            positioning=product["positioning"],
            sales_pitch=product["sales_pitch"],
        )

    def product_title(self, product_id: str) -> str:
        return self.product(product_id)["title"]

    def product_ids(self) -> list[str]:
        return list(self.products.keys())

    def default_prices(self) -> dict[str, int]:
        return {product_id: int(data["default_price_rub"]) for product_id, data in self.products.items()}

    def warmups(self) -> list[dict[str, str]]:
        return list(self.funnel["warmups"])

    def segment_warmups(self, segment: str | None) -> list[dict[str, str]]:
        if not segment:
            return self.warmups()
        return list(self.funnel.get("segment_warmups", {}).get(segment, self.warmups()))

    def quiz_questions(self) -> list[dict[str, Any]]:
        return list(self.funnel["quiz"]["questions"])

    @property
    def services(self) -> dict[str, Any]:
        return self.data.get("services", {})

    @property
    def lead_magnets(self) -> dict[str, Any]:
        return self.data.get("lead_magnets", {})

    @property
    def mini_courses(self) -> dict[str, Any]:
        return self.data.get("mini_courses", {})

    @property
    def post_purchase(self) -> dict[str, Any]:
        return self.data.get("post_purchase", {})

    def objection_answer(self, text: str) -> str | None:
        normalized = text.lower()
        for key, answer in self.funnel["objections"].items():
            if key in normalized:
                return answer
        return None

    def knowledge_points(self) -> list[str]:
        points: list[str] = []
        for product_id in ["book1", "book2"]:
            product = self.product(product_id)
            points.append(f"{product['title']}: {product['positioning']}")
            for key in ("themes", "audience_signals"):
                for item in product.get(key, []):
                    points.append(f"{product['title']}: {item}")
            for part in product.get("parts", []):
                points.append(f"{product['title']} / {part['title']}: {part['summary']}")
            for story in product.get("stories", []):
                points.append(f"{product['title']} / {story['title']}: {story['summary']}")
        points.append(f"{self.product('bundle')['title']}: {self.product('bundle')['positioning']}")
        return points


def _repair_content(data: dict[str, Any]) -> dict[str, Any]:
    """Restore important Russian texts if a hosting/build step damaged JSON encoding."""
    products = data.setdefault("products", {})
    products.update(_inside_bot_products())

    funnel = data.setdefault("funnel", {})
    funnel["welcome"] = (
        "Я помогу выбрать книгу, пройти диагностику, получить бесплатный смысловой материал, "
        "задать вопрос ИИ-консультанту и купить книги прямо здесь, внутри бота."
    )
    funnel["consent"] = (
        "Могу присылать прогрев внутри бота: короткие смыслы, вопросы, бонусные материалы "
        "и редкие предложения. Только по вашему согласию; /stop отключает все рассылки."
    )
    funnel["main_menu"] = (
        "Выберите следующий шаг. Лучше начать с диагностики: она покажет ваш сегмент, "
        "главную боль и точную рекомендацию."
    )
    funnel["quiz"] = _diagnostic_quiz()
    funnel["warmup_schedule"] = {
        "recommended_interval_hours": 24,
        "logic": (
            "Первые 3 касания ежедневно, затем раз в 2-3 дня. Только пользователям с согласием. "
            "После покупки прогрев меняется на план чтения и мягкое предложение второй книги или услуги."
        ),
    }
    funnel["segment_warmups"] = _segment_warmups()
    funnel["fallbacks"] = {
        "unclear": (
            "Я не уверен, что понял запрос. Могу предложить три безопасных шага: пройти диагностику, "
            "посмотреть каталог или задать вопрос иначе - например, что вам ближе: тишина и мистика "
            "или смысл и фантастика?"
        ),
        "after_no_purchase": (
            "Не буду давить. Можно сохранить контакт через прогрев: я пришлю несколько коротких "
            "смысловых сообщений, и вы спокойно решите позже."
        ),
        "after_purchase": "После покупки я могу составить персональный план чтения внутри бота: команда /plan.",
    }
    funnel["ab_offers"] = _ab_offers()

    data["services"] = _services()
    data["lead_magnets"] = {
        "choice_guide": {
            "title": "Как выбрать книгу по состоянию",
            "body": (
                "Если хочется тишины, трав, воды, дома и внутренней силы - начните с "
                "«Ведьмы чёрной воды». Если хочется смысла, технологий, апокалипсиса, "
                "выгорания и разных сюжетов - начните со «Сборника рассказов». Если "
                "откликается и то и другое - комплект честнее и выгоднее."
            ),
            "cta": "Лучший следующий шаг - диагностика из 5 вопросов.",
        }
    }
    data["mini_courses"] = _mini_courses()
    data["post_purchase"] = _post_purchase()
    return data


def _inside_bot_products() -> dict[str, dict[str, Any]]:
    return {
        "deep_reading": {
            "title": "Глубокий ИИ-разбор ситуации в боте",
            "short_title": "ИИ-разбор ситуации",
            "default_price_rub": 900,
            "type": "service",
            "positioning": (
                "Платный персональный разбор внутри бота: пользователь описывает ситуацию, "
                "а консультант связывает ее с темами книг, показывает внутренний конфликт, "
                "возможный читательский маршрут и мягкий план действий."
            ),
            "reader_promise": (
                "Для человека, который хочет не просто выбрать книгу, а понять, какой сюжет "
                "и какие смыслы сейчас точнее попадают в его состояние."
            ),
            "sales_pitch": (
                "Если вопрос личный и хочется не общей рекомендации, а развернутого ответа "
                "по вашей ситуации, берите глубокий ИИ-разбор. Он проходит прямо в боте: "
                "после оплаты отправьте /deep и описание ситуации."
            ),
        },
        "book1_plus_reading": {
            "title": "Ведьма чёрной воды + персональный разбор",
            "short_title": "Книга 1 + разбор",
            "default_price_rub": 2200,
            "type": "package",
            "positioning": (
                "Книга о Чёрной Воде плюс персональный ИИ-разбор внутри бота для читателя, "
                "которому близки травничество, тишина, женская сила, утрата и принятие себя."
            ),
            "reader_promise": (
                "Вы получаете PDF и отдельный разбор, который помогает войти в книгу через "
                "вашу ситуацию, а не через сухое описание."
            ),
            "sales_pitch": (
                "Подходит, если «Ведьма чёрной воды» уже цепляет, но хочется персонального "
                "входа: почему именно эта история может сработать для вас сейчас."
            ),
        },
        "book2_plus_reading": {
            "title": "Сборник рассказов + персональный разбор",
            "short_title": "Книга 2 + разбор",
            "default_price_rub": 2200,
            "type": "package",
            "positioning": (
                "Сборник рассказов плюс персональный ИИ-разбор внутри бота для тех, кому "
                "близки смысл, технологии, апокалипсис, выгорание и выбор."
            ),
            "reader_promise": (
                "Вы получаете PDF и персональную навигацию: с какого рассказа начать и "
                "какие смыслы читать внимательнее."
            ),
            "sales_pitch": (
                "Подходит, если вам нужен не только сборник, но и точная карта входа: "
                "какие рассказы лучше отвечают на ваш текущий вопрос."
            ),
        },
        "bundle_bonus": {
            "title": "Комплект книг + бонусные материалы в боте",
            "short_title": "Комплект + бонусы",
            "default_price_rub": 2400,
            "type": "package",
            "positioning": (
                "Две книги, бонусный внутриботовый гид по чтению, мини-курс и персональный "
                "план после покупки. Все материалы выдаются в этом же боте."
            ),
            "reader_promise": (
                "Максимальная ценность без внешних каналов: книги, смысловая навигация, "
                "бонусы и план чтения внутри Telegram."
            ),
            "sales_pitch": (
                "Лучший вариант, если вы хотите авторский мир целиком. Цена как у комплекта, "
                "но дополнительно бот выдает бонусный гид, мини-курс и персональный план чтения."
            ),
        },
        "mini_course_plus": {
            "title": "Мини-курс «Тихая вода внутри»",
            "short_title": "Мини-курс в боте",
            "default_price_rub": 600,
            "type": "service",
            "positioning": (
                "Платная цепочка из пяти сообщений и практик внутри бота по мотивам обеих книг: "
                "тишина, страх, выбор, связь, план чтения."
            ),
            "reader_promise": (
                "Для тех, кто хочет не только купить книгу, но и прожить темы через короткие "
                "вопросы и упражнения."
            ),
            "sales_pitch": (
                "Мини-курс подходит как мягкий вход перед покупкой или как усиление после нее. "
                "Все уроки приходят и открываются внутри бота."
            ),
        },
    }


def _diagnostic_quiz() -> dict[str, Any]:
    return {
        "intro": (
            "Ответьте на 5 вопросов. Я определю ваш читательский сегмент, готовность к покупке "
            "и подберу книгу, комплект или услугу без давления."
        ),
        "questions": [
            {
                "id": "mood",
                "text": "Что сейчас сильнее откликается?",
                "options": [
                    {"label": "Тишина, лес, вода", "tag": "nature_magic"},
                    {"label": "Смысл и устройство мира", "tag": "philosophy"},
                    {"label": "Выгорание и одиночество", "tag": "burnout"},
                    {"label": "Тёмная атмосфера", "tag": "dark"},
                ],
            },
            {
                "id": "pain",
                "text": "Какая боль ближе?",
                "options": [
                    {"label": "Слишком много шума", "tag": "quiet"},
                    {"label": "Не хватает опоры", "tag": "roots"},
                    {"label": "Не понимаю, куда двигаться", "tag": "lost"},
                    {"label": "Нет времени читать", "tag": "no_time"},
                ],
            },
            {
                "id": "format",
                "text": "Какой формат чтения нужен?",
                "options": [
                    {"label": "Одна глубокая история", "tag": "long_story"},
                    {"label": "Несколько рассказов", "tag": "short_stories"},
                    {"label": "Хочу всё целиком", "tag": "complete_world"},
                ],
            },
            {
                "id": "motivation",
                "text": "Зачем вам книга сейчас?",
                "options": [
                    {"label": "Вернуть внутреннюю тишину", "tag": "healing"},
                    {"label": "Понять себя", "tag": "meaning"},
                    {"label": "Подарить или посоветовать", "tag": "share"},
                    {"label": "Просто выбрать без ошибки", "tag": "doubt"},
                ],
            },
            {
                "id": "readiness",
                "text": "Насколько вы готовы к покупке?",
                "options": [
                    {"label": "Готов купить сейчас", "tag": "ready_now"},
                    {"label": "Хочу сначала прогреться", "tag": "warmup_needed"},
                    {"label": "Сомневаюсь в цене", "tag": "expensive"},
                    {"label": "Нужна консультация", "tag": "consult_needed"},
                ],
            },
        ],
    }


def _segment_warmups() -> dict[str, list[dict[str, str]]]:
    return {
        "quiet_roots": [
            {
                "key": "quiet_1",
                "title": "Почему Чёрная Вода начинается с тишины",
                "body": (
                    "В первой книге сильнее всего работает не внешняя магия, а состояние: "
                    "утренний чай, травы, дом, болото, дневник, медленное возвращение к себе."
                ),
                "cta": "Ваш главный вход: «Ведьма чёрной воды» или комплект, если хочется увидеть шире.",
            },
            {
                "key": "quiet_2",
                "title": "Тьма, которой нашли место",
                "body": (
                    "Алёна не побеждает тьму красивым жестом. Она учится не отдавать ей власть. "
                    "В этом ценность книги для взрослого читателя."
                ),
                "cta": "Если это откликается, начните с первой книги.",
            },
        ],
        "meaning_system": [
            {
                "key": "meaning_1",
                "title": "Фантастика как вопрос о смысле",
                "body": (
                    "Во второй книге рассказы работают как разные эксперименты: что если реальность - Игра, "
                    "деньги обнулятся, город станет цифровым двойником, а одиночество получит голос?"
                ),
                "cta": "Ваш вход: «Сборник рассказов» или комплект.",
            }
        ],
        "burnout_mirror": [
            {
                "key": "burnout_1",
                "title": "Когда жизнь стала автоматической",
                "body": (
                    "В сборнике есть герои, которые живут на автопилоте: работа, тревога, чужие ожидания, "
                    "одиночество. В первой книге похожий нерв выражен через дом, утрату и сад."
                ),
                "cta": "Если сомневаетесь между форматами, комплект даст оба зеркала.",
            }
        ],
        "dark_atmosphere": [
            {
                "key": "dark_1",
                "title": "Темная атмосфера без пустого хоррора",
                "body": (
                    "Чёрная Вода, Сердцепуст, поселок Лесной, завод, страх и вина - это не декорации "
                    "ради мрака. Через темные образы книги говорят о принятии и выборе."
                ),
                "cta": "Если любите плотную мистику, лучше брать комплект.",
            }
        ],
        "complete_world": [
            {
                "key": "bundle_1",
                "title": "Почему комплект сильнее одной книги",
                "body": (
                    "Первая книга дает медленную глубину: вода, травы, дом, сила и равновесие. "
                    "Вторая дает широту: Творец и Игра, апокалипсис, цифровая Москва, эмпатия, выгорание."
                ),
                "cta": "Две книги отдельно стоят 3000, комплект - 2400.",
            }
        ],
    }


def _ab_offers() -> dict[str, list[str]]:
    return {
        "book1": [
            "Вариант A: «Ведьма чёрной воды» - для тех, кому нужна тишина, корни, травы и взрослая история о принятии своей силы.",
            "Вариант B: Если внутри много шума, начните с книги, где магия проявляется через заботу, сад, воду и способность жить дальше.",
        ],
        "book2": [
            "Вариант A: «Сборник рассказов» - семь зеркал о смысле, технологиях, апокалипсисе, одиночестве и выборе.",
            "Вариант B: Если хочется не одного сюжета, а серии сильных идей с послевкусием, берите сборник.",
        ],
        "bundle": [
            "Вариант A: Комплект - полный авторский мир дешевле, чем две книги по отдельности.",
            "Вариант B: Если сомневаетесь между тишиной Чёрной Воды и философской фантастикой, берите комплект.",
        ],
    }


def _services() -> dict[str, dict[str, str]]:
    return {
        "lead_magnet": {
            "title": "Бесплатный лид-магнит «Как выбрать книгу по состоянию»",
            "value": "Помогает понять, какая книга сейчас ближе: мистическая тишина, философская фантастика или комплект.",
            "audience": "Новые пользователи и сомневающиеся.",
            "funnel_place": "До диагностики или сразу после первого визита.",
            "scenario": "Кнопка в меню открывает короткий внутриботовый гид и ведет к диагностике.",
        },
        "diagnostic": {
            "title": "Персональная диагностика читательского состояния",
            "value": "Сегментирует пользователя по интересу, боли, мотивации и готовности к покупке.",
            "audience": "Все новые пользователи.",
            "funnel_place": "Главная точка входа перед продажей.",
            "scenario": "5 вопросов, профиль, рекомендация, оффер и кнопки покупки/консультации.",
        },
        "deep_reading": {
            "title": "Платный ИИ-разбор ситуации",
            "value": "Пользователь получает развернутую интерпретацию своей ситуации через темы книг.",
            "audience": "Люди с личным запросом, сомнением или высоким интересом.",
            "funnel_place": "После диагностики, вопроса консультанту или покупки.",
            "scenario": "Покупка услуги, затем команда /deep с описанием ситуации, ответ внутри бота.",
        },
    }


def _mini_courses() -> dict[str, dict[str, Any]]:
    return {
        "quiet_water": {
            "title": "Тихая вода внутри",
            "lessons": [
                {
                    "title": "Урок 1. Что шумит внутри",
                    "body": "В книгах шум принимает разные формы: деревенский страх, новости апокалипсиса, цифровой город, рутина.",
                    "practice": "Ответьте себе: что сейчас забирает больше всего внимания?",
                    "cta": "Если нужен мягкий вход, пройдите диагностику.",
                },
                {
                    "title": "Урок 2. Где ваша Чёрная Вода",
                    "body": "Чёрная Вода - это место силы и страха одновременно. У каждого есть область, к которой тянет и от которой тревожно.",
                    "practice": "Напишите одно место, тему или решение, которое вы откладываете.",
                    "cta": "Если тянет к этой теме, вам подойдет первая книга.",
                },
                {
                    "title": "Урок 3. Что обнуляется в кризис",
                    "body": "В «3 дня апокалипсиса» деньги и статусы теряют вес. Остаются вода, хлеб, связь и помощь.",
                    "practice": "Что останется важным, если убрать внешнюю гонку?",
                    "cta": "Если откликается, посмотрите сборник.",
                },
                {
                    "title": "Урок 4. Тень как часть сада",
                    "body": "В линии Чёрной Воды важна не победа над всем темным, а равновесие: каждому растению свое место.",
                    "practice": "Какую часть себя вы пытаетесь вырвать, хотя ей нужно место?",
                    "cta": "Для глубины берите «Ведьму чёрной воды».",
                },
                {
                    "title": "Урок 5. Ваш маршрут чтения",
                    "body": "Если вам нужна тишина - начинайте с первой книги. Если нужны идеи - со второй. Если видите оба слоя, берите комплект.",
                    "practice": "Выберите один шаг: купить книгу, комплект или задать вопрос консультанту.",
                    "cta": "Каталог доступен прямо в боте.",
                },
            ],
        }
    }


def _post_purchase() -> dict[str, Any]:
    return {
        "plan_intro": "Персональный план чтения внутри бота строится по вашим тегам диагностики и купленным материалам.",
        "plans": {
            "book1": [
                "Читайте по 1-2 главы вечером без параллельного шума.",
                "Отмечайте сцены про дом, травы, воду и сад.",
                "После каждой части спросите себя: какую тьму герой не уничтожил, а встроил в жизнь?",
            ],
            "book2": [
                "Выберите первый рассказ по состоянию: смысл - «Код бытия», тревога - «3 дня апокалипсиса», выгорание - «Созвездие».",
                "После каждого рассказа запишите один вопрос, который остался.",
                "Если рассказ задел, вернитесь к нему через день.",
            ],
            "bundle": [
                "Начните с той книги, которую выдала диагностика.",
                "Затем прочитайте 2-3 рассказа из сборника как контраст.",
                "Используйте мини-курс в боте как навигацию по смыслам.",
            ],
        },
    }
