from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from pathlib import Path
from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    user_models_enabled: bool = False
    user_model_secret_backend: Literal["auto", "windows_dpapi", "aesgcm_file"] = "auto"
    user_model_master_key_file: str = ""
    translation_mock_enabled: bool = False
    unified_acceptance: bool = False
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


class ModelSettings(BaseSettings):
    """Developer-local AI configuration, separate from all business and DB settings."""
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)
    provider: str = Field(default="openai_compatible", validation_alias=AliasChoices("AI_PROVIDER", "TRANSLATION_PROVIDER"))
    base_url: str = Field(default="", validation_alias=AliasChoices("AI_BASE_URL", "TRANSLATION_BASE_URL"))
    model: str = Field(default="", validation_alias=AliasChoices("AI_MODEL", "TRANSLATION_MODEL"))
    api_key: SecretStr | None = Field(default=None, repr=False, validation_alias=AliasChoices("AI_API_KEY", "TRANSLATION_API_KEY"))
    verified: bool = Field(default=False, validation_alias=AliasChoices("AI_MODEL_VERIFIED", "TRANSLATION_MODEL_VERIFIED"))

    max_output_tokens: int = Field(default=2048, ge=16, le=4096, validation_alias="AI_MAX_OUTPUT_TOKENS")

    embedding_model: str = Field(default="course-embedding", validation_alias=AliasChoices("AI_EMBEDDING_MODEL"))
    embedding_dim: int = Field(default=2048, ge=1, le=8192, validation_alias="AI_EMBEDDING_DIM")
    embedding_verified: bool = Field(default=False, validation_alias="AI_EMBEDDING_MODEL_VERIFIED")
    # Optional separate endpoint/key for embeddings (e.g. chat on DeepSeek, embeddings on a gateway that offers them).
    embedding_base_url: str = Field(default="", validation_alias="AI_EMBEDDING_BASE_URL")
    embedding_api_key: SecretStr | None = Field(default=None, repr=False, validation_alias="AI_EMBEDDING_API_KEY")

    qa_top_k: int = Field(default=8, ge=1, le=30, validation_alias="QA_TOP_K")
    qa_recall_k: int = Field(default=30, ge=1, le=100, validation_alias="QA_RECALL_K")
    qa_max_context_chars: int = Field(default=6000, ge=500, le=30000, validation_alias="QA_MAX_CONTEXT_CHARS")
    qa_analysis_max_chars: int = Field(default=12000, ge=500, le=60000, validation_alias="QA_ANALYSIS_MAX_CHARS")
    qa_min_similarity: float = Field(default=0.25, ge=0, le=1, validation_alias="QA_MIN_SIMILARITY")
    qa_timeout_seconds: int = Field(default=60, ge=5, le=300, validation_alias="QA_TIMEOUT_SECONDS")
    qa_index_sweep_seconds: int = Field(default=60, ge=10, le=3600, validation_alias="QA_INDEX_SWEEP_SECONDS")
    qa_index_batch: int = Field(default=32, ge=1, le=64, validation_alias="QA_INDEX_BATCH")

    # Compatibility for existing translation callers/configuration, not a second key store.
    @property
    def translation_provider(self): return self.provider
    @property
    def translation_base_url(self): return self.base_url
    @property
    def translation_model(self): return self.model
    @property
    def translation_api_key(self): return self.api_key
    @property
    def translation_model_verified(self): return self.verified

@lru_cache
def get_model_settings():
    import os
    path = Path(__file__).resolve().parents[1] / ".env"
    return ModelSettings(_env_file=None if (os.environ.get("APP_ENV") == "test" or os.environ.get("LITERA_DISABLE_DEVELOPER_MODEL") == "1") else path)

TranslationSettings = ModelSettings
get_translation_settings = get_model_settings
