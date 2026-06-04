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
            return cls(json.loads(path.read_text(encoding="utf-8")))

        fallback = resources.files("book_sales_bot").joinpath("default_content.json")
        return cls(json.loads(fallback.read_text(encoding="utf-8")))

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
