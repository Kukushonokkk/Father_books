from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    return float(value)


def _ids(value: str | None) -> set[int]:
    if not value:
        return set()
    result: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            result.add(int(item))
    return result


def _path(value: str | None, default: str) -> Path:
    raw = value or default
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


@dataclass(frozen=True)
class Config:
    bot_token: str
    telegram_proxy_url: str
    telegram_request_timeout: float
    admin_ids: set[int]
    database_path: Path
    content_path: Path
    book1_file_path: Path
    book2_file_path: Path
    book_price_rub: int
    bundle_price_rub: int
    payment_mode: str
    payment_provider_name: str
    telegram_provider_token: str
    payment_currency: str
    manual_payment_details: str
    yoomoney_card_number: str
    enable_test_payments: bool
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_temperature: float
    warmup_enabled: bool
    warmup_interval_hours: int
    max_broadcast_per_minute: int

    @property
    def product_files(self) -> dict[str, list[Path]]:
        return {
            "book1": [self.book1_file_path],
            "book2": [self.book2_file_path],
            "bundle": [self.book1_file_path, self.book2_file_path],
        }


def load_config() -> Config:
    load_dotenv(PROJECT_ROOT / ".env")
    payment_mode = os.getenv("PAYMENT_MODE", "test").strip().lower()
    if payment_mode not in {"test", "manual", "telegram", "yoomoney"}:
        raise ValueError("PAYMENT_MODE must be one of: test, manual, telegram, yoomoney")

    return Config(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        telegram_proxy_url=os.getenv("TELEGRAM_PROXY_URL", "").strip(),
        telegram_request_timeout=_float(os.getenv("TELEGRAM_REQUEST_TIMEOUT"), 60.0),
        admin_ids=_ids(os.getenv("ADMIN_IDS")),
        database_path=_path(os.getenv("DATABASE_PATH"), "data/bot.sqlite3"),
        content_path=_path(os.getenv("CONTENT_PATH"), "data/content.json"),
        book1_file_path=_path(os.getenv("BOOK1_FILE_PATH"), "книга 1.pdf"),
        book2_file_path=_path(os.getenv("BOOK2_FILE_PATH"), "книга 2.pdf"),
        book_price_rub=_int(os.getenv("BOOK_PRICE_RUB"), 1500),
        bundle_price_rub=_int(os.getenv("BUNDLE_PRICE_RUB"), 2400),
        payment_mode=payment_mode,
        payment_provider_name=os.getenv("PAYMENT_PROVIDER_NAME", "ЮMoney").strip(),
        telegram_provider_token=os.getenv("TELEGRAM_PROVIDER_TOKEN", "").strip(),
        payment_currency=os.getenv("PAYMENT_CURRENCY", "RUB").strip().upper(),
        manual_payment_details=os.getenv("MANUAL_PAYMENT_DETAILS", "").strip(),
        yoomoney_card_number=os.getenv("YOOMONEY_CARD_NUMBER", "").strip(),
        enable_test_payments=_bool(os.getenv("ENABLE_TEST_PAYMENTS"), True),
        ai_api_key=os.getenv("AI_API_KEY", "").strip(),
        ai_base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/"),
        ai_model=os.getenv("AI_MODEL", "").strip(),
        ai_temperature=_float(os.getenv("AI_TEMPERATURE"), 0.2),
        warmup_enabled=_bool(os.getenv("WARMUP_ENABLED"), True),
        warmup_interval_hours=_int(os.getenv("WARMUP_INTERVAL_HOURS"), 24),
        max_broadcast_per_minute=_int(os.getenv("MAX_BROADCAST_PER_MINUTE"), 20),
    )
