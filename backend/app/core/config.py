from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENVIRONMENTS = {"development", "staging", "production"}
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    DATABASE_URL_UNPOOLED: str = ""
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str = "redis://localhost:6379/0"
    # Defaults to production so a missing setting can never silently turn off
    # Secure cookies, HSTS or strict rate limits. Local .env files set it.
    ENVIRONMENT: str = "production"
    # Shared with the Cloudflare Worker. When set, the API trusts the worker's
    # client IP header only on requests carrying this exact secret.
    PROXY_SHARED_SECRET: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "onboarding@resend.dev"
    PRODUCT_ENQUIRY_EMAIL: str = ""
    BILLING_SUPPORT_EMAIL: str = "mahaba955@gmail.com"
    BACKUP_SIGNING_KEY: str = ""
    PG_DUMP_PATH: str = ""
    PG_RESTORE_PATH: str = ""
    RESTORE_DATABASE_URL: str = ""
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _fail_closed(self):
        if self.ENVIRONMENT not in ENVIRONMENTS:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(ENVIRONMENTS)}")
        if not self.is_development:
            if len(self.JWT_SECRET_KEY) < MIN_SECRET_LENGTH:
                raise ValueError(f"JWT_SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters outside development")
            if self.PROXY_SHARED_SECRET and len(self.PROXY_SHARED_SECRET) < MIN_SECRET_LENGTH:
                raise ValueError(f"PROXY_SHARED_SECRET must be at least {MIN_SECRET_LENGTH} characters")
        return self

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def cookie_secure(self) -> bool:
        # Cookies marked "Secure" are only sent over HTTPS. Localhost dev
        # runs over plain HTTP, so this must be False in development or
        # browsers will silently refuse to store the cookie at all.
        return not self.is_development


settings = Settings()
