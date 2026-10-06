"""Application settings loaded from environment variables and the local .env file."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "word_explainer")
    db_user: str = os.getenv("DB_USER", "word_explainer")
    db_password: str = os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", ""))


settings = Settings()
