"""Central configuration loaded from environment variables (.env supported)."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DUCKDB_PATH = os.getenv("DUCKDB_PATH", str(ROOT / "warehouse.duckdb"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501").rstrip("/")
DASHBOARD_URL_ZH = os.getenv("DASHBOARD_URL_ZH", f"{DASHBOARD_URL}/?lang=zh")
DASHBOARD_URL_EN = os.getenv("DASHBOARD_URL_EN", f"{DASHBOARD_URL}/?lang=en")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
# accept both SMTP_PASSWORD and SMTP_PASS (the name used in the email brief)
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS", "")
MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USER or "noreply@localhost")
MAIL_TO = os.getenv("MAIL_TO", "dingbangchu@gmail.com")

LARK_WEBHOOK = os.getenv("LARK_WEBHOOK", "")

REPORTS_DIR = ROOT / "reports"
RESULTS_DIR = REPORTS_DIR / "results"
SCREENSHOT_PATH = REPORTS_DIR / "dashboard_screenshot_zh.png"
SCREENSHOT_PATH_EN = REPORTS_DIR / "dashboard_screenshot_en.png"
SCREENSHOT_LEGACY = REPORTS_DIR / "dashboard_screenshot.png"
