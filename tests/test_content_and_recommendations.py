from __future__ import annotations

import json
import unittest
from pathlib import Path

from book_sales_bot.recommendations import recommend_by_tags, recommend_by_text
from book_sales_bot.segmentation import build_profile


ROOT = Path(__file__).resolve().parents[1]


class ContentAndRecommendationTests(unittest.TestCase):
    def test_content_has_required_products_and_prices(self) -> None:
        data = json.loads((ROOT / "data" / "content.json").read_text(encoding="utf-8"))
        self.assertIn("book1", data["products"])
        self.assertIn("book2", data["products"])
        self.assertIn("bundle", data["products"])
        self.assertIn("bundle_bonus", data["products"])
        self.assertIn("deep_reading", data["products"])
        self.assertEqual(data["products"]["book1"]["default_price_rub"], 1500)
        self.assertEqual(data["products"]["book2"]["default_price_rub"], 1500)
        self.assertEqual(data["products"]["bundle"]["default_price_rub"], 2400)
        self.assertGreaterEqual(len(data["funnel"]["warmups"]), 5)
        self.assertEqual(len(data["funnel"]["quiz"]["questions"]), 5)
        self.assertIn("segment_warmups", data["funnel"])
        self.assertIn("mini_courses", data)

    def test_recommend_book1_for_nature_magic(self) -> None:
        rec = recommend_by_tags(["nature_magic", "long_story"])
        self.assertEqual(rec.product_id, "book1")

    def test_recommend_book2_for_philosophy_and_stories(self) -> None:
        rec = recommend_by_tags(["philosophy", "short_stories"])
        self.assertEqual(rec.product_id, "book2")

    def test_recommend_bundle_for_mixed_interest(self) -> None:
        rec = recommend_by_tags(["nature_magic", "philosophy"])
        self.assertEqual(rec.product_id, "bundle")

    def test_recommend_from_free_text(self) -> None:
        rec = recommend_by_text("Мне интересны ведьма, лес, травы и одиночество")
        self.assertEqual(rec.product_id, "book1")
        rec = recommend_by_text("Хочу философскую фантастику про технологии и смысл")
        self.assertEqual(rec.product_id, "book2")

    def test_segmentation_profile(self) -> None:
        profile = build_profile(["nature_magic", "quiet", "long_story", "healing"])
        self.assertEqual(profile.segment, "quiet_roots")
        self.assertEqual(profile.recommended_product_id, "book1")
        self.assertGreaterEqual(profile.readiness_score, 30)


if __name__ == "__main__":
    unittest.main()
