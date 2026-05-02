"""Carga la configuración desde variables de entorno (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _default_database_url() -> str:
    """SQLite local por defecto. En produccion se sobreescribe con DATABASE_URL."""
    return f"sqlite:///{BASE_DIR / 'radar.db'}"


@dataclass(frozen=True)
class Config:
    base_dir: Path = BASE_DIR
    logs_dir: Path = BASE_DIR / "logs"

    database_url: str = (
        os.getenv("DATABASE_URL", _default_database_url())
        .replace("postgres://", "postgresql://", 1)
    )

    flask_secret_key: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/")

    app_password: str = os.getenv("APP_PASSWORD", "SaintPeter")

    brevo_api_key: str = os.getenv("BREVO_API_KEY", "").strip()
    brevo_sender_email: str = os.getenv("BREVO_SENDER_EMAIL", "alertas@example.com").strip()
    brevo_sender_name: str = os.getenv("BREVO_SENDER_NAME", "Radar Regulatorio").strip()

    daily_job_time: str = os.getenv("DAILY_JOB_TIME", "10:00").strip()

    ingest_lookback_days: int = int(os.getenv("INGEST_LOOKBACK_DAYS", "95"))
    display_window_days: int = int(os.getenv("DISPLAY_WINDOW_DAYS", "92"))


config = Config()
config.logs_dir.mkdir(exist_ok=True)
