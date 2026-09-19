from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'pragati-bharati'
    app_env: str = 'development'
    debug: bool = True
    database_url: str = 'sqlite+aiosqlite:///./app.db'
    redis_url: str = 'redis://localhost:6379/0'
    jwt_secret: str = 'pragati-bharati-super-secure-production-secret-key-2026'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    upload_dir: str = './storage/uploads'
    max_upload_size: int = 15 * 1024 * 1024  # 15 MB
    allowed_mime_types: List[str] = [
        'application/pdf',
        'image/jpeg',
        'image/png',
        'image/jpg',
    ]
    allowed_extensions: List[str] = ['.pdf', '.png', '.jpg', '.jpeg']
    ocr_confidence_threshold: float = 0.65
    tesseract_cmd: str | None = None

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
