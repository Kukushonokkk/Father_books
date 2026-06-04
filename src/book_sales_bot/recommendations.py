from __future__ import annotations

from dataclasses import dataclass


BOOK1_TAGS = {"nature_magic", "long_story", "roots", "healing", "female_power", "quiet"}
BOOK2_TAGS = {"philosophy", "apocalypse", "burnout", "short_stories", "technology", "city", "meaning", "lost"}
BUNDLE_TAGS = {"complete_world", "mixed", "both", "dark"}

BOOK1_KEYWORDS = {
    "ведьма",
    "трав",
    "лес",
    "болот",
    "вода",
    "алён",
    "алена",
    "женск",
    "одиночеств",
    "исцелен",
    "дом",
    "корн",
    "маг",
}
BOOK2_KEYWORDS = {
    "смысл",
    "философ",
    "фантаст",
    "апокалип",
    "цифров",
    "симуляц",
    "код",
    "игр",
    "выгоран",
    "одиночеств",
    "технолог",
    "рассказ",
}


@dataclass(frozen=True)
class Recommendation:
    product_id: str
    reason: str


def recommend_by_tags(tags: list[str], owned: list[str] | None = None) -> Recommendation:
    owned = owned or []
    tag_set = set(tags)
    if "bundle" in owned:
        return Recommendation("bundle", "У вас уже отмечен интерес к полному авторскому миру.")
    if "book1" in owned and "book2" not in owned:
        return Recommendation("book2", "После «Ведьмы чёрной воды» логично взять сборник, чтобы увидеть другие грани авторского мира.")
    if "book2" in owned and "book1" not in owned:
        return Recommendation("book1", "После сборника хорошо зайдет цельная мистическая история о Чёрной Воде.")

    book1_score = len(tag_set & BOOK1_TAGS)
    book2_score = len(tag_set & BOOK2_TAGS)
    bundle_score = len(tag_set & BUNDLE_TAGS)

    if bundle_score or (book1_score > 0 and book2_score > 0):
        return Recommendation("bundle", "У вас смешанный запрос: и глубокая мистическая линия, и философско-фантастические темы. Комплект даст полный эффект и выгоднее по цене.")
    if book1_score >= book2_score and book1_score > 0:
        return Recommendation("book1", "По вашим ответам ближе медленное атмосферное погружение: природа, Чёрная Вода, травничество, одиночество и внутренняя сила.")
    if book2_score > 0:
        return Recommendation("book2", "По вашим ответам ближе сборник: смысл, технологии, тревога, апокалипсис, выгорание и несколько сильных историй.")
    return Recommendation("bundle", "Пока запрос широкий, поэтому лучше показать обе книги как единый авторский мир.")


def recommend_by_text(text: str, owned: list[str] | None = None) -> Recommendation:
    owned = owned or []
    if "bundle" in owned:
        return Recommendation("bundle", "У вас уже отмечен интерес к полному авторскому миру.")
    if "book1" in owned and "book2" not in owned:
        return Recommendation("book2", "После «Ведьмы чёрной воды» логично взять сборник, чтобы увидеть другие грани авторского мира.")
    if "book2" in owned and "book1" not in owned:
        return Recommendation("book1", "После сборника хорошо зайдет цельная мистическая история о Чёрной Воде.")

    normalized = text.lower()
    if "обе" in normalized or "комплект" in normalized or "всё" in normalized or "все" in normalized:
        return Recommendation("bundle", "Вы прямо рассматриваете обе книги, поэтому комплект будет самым логичным и выгодным вариантом.")

    book1_score = sum(1 for keyword in BOOK1_KEYWORDS if keyword in normalized)
    book2_score = sum(1 for keyword in BOOK2_KEYWORDS if keyword in normalized)

    if book1_score and book2_score:
        if abs(book1_score - book2_score) <= 1:
            return Recommendation("bundle", "В запросе смешались мотивы обеих книг, поэтому комплект даст более полный эффект.")
        if book1_score > book2_score:
            return Recommendation("book1", "В запросе сильнее звучат мотивы Чёрной Воды: природа, ведьма, травы, дом и внутренняя тишина.")
        return Recommendation("book2", "В запросе сильнее звучат мотивы сборника: смысл, технологии, фантастика, тревога и разные истории.")
    if book1_score:
        return Recommendation("book1", "В запросе сильнее звучат мотивы Чёрной Воды: природа, ведьма, травы, дом и внутренняя тишина.")
    if book2_score:
        return Recommendation("book2", "В запросе сильнее звучат мотивы сборника: смысл, технологии, фантастика, тревога и разные истории.")
    return recommend_by_tags([], owned)
