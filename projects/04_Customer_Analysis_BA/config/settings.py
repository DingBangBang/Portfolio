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
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USER or "noreply@localhost")
MAIL_TO = os.getenv("MAIL_TO", "dingbangchu@gmail.com")

REPORTS_DIR = ROOT / "reports"
SCREENSHOT_PATH = REPORTS_DIR / "dashboard_screenshot.png"
