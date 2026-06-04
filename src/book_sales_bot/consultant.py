from __future__ import annotations

import aiohttp

from .config import Config
from .content import ContentStore
from .database import Database
from .recommendations import recommend_by_text


class Consultant:
    def __init__(self, config: Config, content: ContentStore, db: Database) -> None:
        self.config = config
        self.content = content
        self.db = db

    async def answer(self, user_id: int, question: str) -> tuple[str, str]:
        if len(question.strip()) < 4:
            return self.content.funnel.get("fallbacks", {}).get("unclear", "Уточните запрос одним сообщением."), "bundle"

        objection = self.content.objection_answer(question)
        owned = self.db.user_purchases(user_id)
        recommendation = recommend_by_text(question, owned)
        if objection:
            return f"{objection}\n\nРекомендация: {self.content.product_title(recommendation.product_id)}.", recommendation.product_id

        if self.config.ai_api_key and self.config.ai_model:
            ai_answer = await self._remote_answer(user_id, question, recommendation.product_id)
            if ai_answer:
                return ai_answer, recommendation.product_id

        return self._local_answer(user_id, question, recommendation.product_id), recommendation.product_id

    def _local_answer(self, user_id: int, question: str, product_id: str) -> str:
        product = self.content.product(product_id)
        if product_id == "bundle":
            pitch = product["sales_pitch"]
        else:
            pitch = product["sales_pitch"]

        relevant_points = self._relevant_points(question)
        if not relevant_points:
            fallback = self.content.funnel.get("fallbacks", {}).get("unclear")
            relevant_points = [self.content.product(product_id)["positioning"]]
        else:
            fallback = None

        profile = self.db.get_profile(user_id)

        lines = [
            "Отвечу как консультант по этим двум книгам.",
            "",
        *[f"- {point}" for point in relevant_points[:3]],
            "",
            pitch,
            "",
            f"Моя рекомендация сейчас: {self.content.product_title(product_id)}.",
        ]
        if profile:
            lines.insert(2, f"Ваш сегмент диагностики: {profile['segment']}, готовность {profile['readiness_score']}/100.")
            lines.insert(3, "")
        if fallback:
            lines.append("")
            lines.append(fallback)
        return "\n".join(lines)

    def _relevant_points(self, question: str) -> list[str]:
        normalized = question.lower()
        scored: list[tuple[int, str]] = []
        for point in self.content.knowledge_points():
            score = 0
            for token in normalized.split():
                token = token.strip(".,!?;:()[]«»\"'")
                if len(token) >= 4 and token in point.lower():
                    score += 1
            if score:
                scored.append((score, point))
        return [point for _, point in sorted(scored, reverse=True)]

    async def _remote_answer(self, user_id: int, question: str, product_id: str) -> str | None:
        context = "\n".join(self.content.knowledge_points()[:80])
        profile = self.db.get_profile(user_id)
        profile_context = ""
        if profile:
            profile_context = (
                f"Профиль пользователя: сегмент={profile['segment']}; "
                f"боль={profile['pain']}; мотивация={profile['motivation']}; "
                f"готовность={profile['readiness_score']}/100."
            )
        system = (
            "Ты консультант Telegram-бота, который продает две книги автора. "
            "Отвечай по-русски, честно, без выдумывания фактов, не раскрывай полный текст книг. "
            "Основывайся только на контексте, помогай выбрать одну книгу, комплект или внутриботовую услугу. "
            "Не отправляй пользователя во внешние каналы, сайты, сообщества или платформы."
        )
        payload = {
            "model": self.config.ai_model,
            "temperature": self.config.ai_temperature,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"Контекст:\n{context}\n\n{profile_context}\n\n"
                        f"Вопрос пользователя:\n{question}\n\nРекомендованный продукт: {product_id}"
                    ),
                },
            ],
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.ai_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.ai_api_key}",
                        "HTTP-Referer": "https://telegram.local/book-sales-bot",
                        "X-Title": "Book Sales Telegram Bot",
                    },
                    json=payload,
                    timeout=30,
                ) as response:
                    if response.status >= 400:
                        return None
                    data = await response.json()
        except Exception:
            return None
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            return None
