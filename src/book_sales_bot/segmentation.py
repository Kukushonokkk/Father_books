from __future__ import annotations

from dataclasses import dataclass

from .recommendations import recommend_by_tags


@dataclass(frozen=True)
class SegmentProfile:
    segment: str
    title: str
    pain: str
    motivation: str
    readiness_score: int
    recommended_product_id: str
    summary: str


SEGMENT_TITLES = {
    "quiet_roots": "Ищущий тишину и корни",
    "meaning_system": "Ищущий смысл и систему",
    "burnout_mirror": "Читатель на перепутье",
    "dark_atmosphere": "Любитель темной атмосферы",
    "complete_world": "Хочет авторский мир целиком",
}


def build_profile(tags: list[str], owned: list[str] | None = None) -> SegmentProfile:
    tag_set = set(tags)
    recommendation = recommend_by_tags(tags, owned)
    readiness_score = _readiness_score(tag_set)

    if "complete_world" in tag_set or recommendation.product_id == "bundle":
        segment = "complete_world"
        pain = "Сложно выбрать одну линию, потому что цепляют и внутренняя тишина, и философская фантастика."
        motivation = "Получить полный авторский мир и не потерять ни глубокую мистическую линию, ни рассказы с сильными идеями."
    elif tag_set & {"nature_magic", "roots", "healing", "female_power", "quiet"}:
        segment = "quiet_roots"
        pain = "Усталость от шума, нехватка внутренней опоры, желание истории, где тьма не отрицается, а получает место."
        motivation = "Найти тихую, атмосферную книгу про дом, травы, воду, силу и бережное возвращение к себе."
    elif tag_set & {"philosophy", "technology", "meaning"}:
        segment = "meaning_system"
        pain = "Хочется не просто развлечения, а вопроса о смысле, устройстве реальности, выборе и человеческом развитии."
        motivation = "Получить набор историй, где фантастика работает как способ думать о жизни, технологиях и человечности."
    elif tag_set & {"burnout", "loneliness", "lost", "no_time"}:
        segment = "burnout_mirror"
        pain = "Рутина, тревога, одиночество или ощущение, что жизнь стала слишком автоматической."
        motivation = "Увидеть себя в героях и получить не совет, а точное художественное зеркало."
    else:
        segment = "dark_atmosphere"
        pain = "Тянет к темной, плотной атмосфере, где страхи и тени становятся частью сюжета."
        motivation = "Прочитать истории с болотной мистикой, поселковой тьмой, внутренними демонами и катарсисом."

    title = SEGMENT_TITLES[segment]
    summary = f"{title}. Главная боль: {pain} Главная мотивация: {motivation} Рекомендация: {recommendation.product_id}."
    return SegmentProfile(
        segment=segment,
        title=title,
        pain=pain,
        motivation=motivation,
        readiness_score=readiness_score,
        recommended_product_id=recommendation.product_id,
        summary=summary,
    )


def _readiness_score(tags: set[str]) -> int:
    score = 35
    if tags & {"ready_now", "complete_world"}:
        score += 30
    if tags & {"doubt", "expensive", "no_time"}:
        score -= 15
    if tags & {"pain_high", "burnout", "lost", "loneliness"}:
        score += 15
    if tags & {"gift", "share"}:
        score += 5
    return max(0, min(100, score))
