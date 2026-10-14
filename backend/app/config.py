from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str
    public_origin: str = "http://localhost:8080"
    session_secret: str = Field(min_length=32)
    cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=86400, ge=60)
    password_min_length: int = Field(default=8, ge=8, le=128)
    auth_rate_limit: int = Field(default=20, ge=1)
    auth_rate_window_seconds: int = Field(default=60, ge=1)
    pdf_storage_root: Path = Path("storage/pdfs")
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, ge=1)

    @model_validator(mode="after")
    def validate_production(self):
        origin = urlsplit(self.public_origin)
        if origin.scheme not in ("http", "https") or not origin.hostname or origin.path or origin.query or origin.fragment:
            raise ValueError("PUBLIC_ORIGIN must be an HTTP(S) origin without path/query/fragment")
        if self.public_origin.rstrip("/") != self.public_origin:
            raise ValueError("PUBLIC_ORIGIN must not end with /")
        if self.app_env == "production" and (
            not self.cookie_secure or not self.public_origin.startswith("https://")
        ):
            raise ValueError("Production requires HTTPS PUBLIC_ORIGIN and COOKIE_SECURE=true")
        return self

@lru_cache
def get_settings():
    return Settings()
