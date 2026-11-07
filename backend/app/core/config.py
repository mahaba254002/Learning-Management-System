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
    # Safaricom Daraja. Empty keys switch M-Pesa payments off.
    MPESA_ENVIRONMENT: str = "sandbox"
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    MPESA_SHORTCODE: str = ""
    MPESA_PASSKEY: str = ""
    # Set for a Buy Goods till; leave empty for a paybill.
    MPESA_TILL_NUMBER: str = ""
    # Public API address Safaricom calls back, e.g. https://api.example.com
    MPESA_CALLBACK_BASE_URL: str = ""
    # Secret path segment in callback URLs; Daraja callbacks carry no signature.
    MPESA_CALLBACK_SECRET: str = ""
    # Optional comma-separated Safaricom callback addresses.
    MPESA_ALLOWED_IPS: str = ""

    # Africa's Talking SMS, paid by the platform. Empty username/key = SMS off.
    AT_ENVIRONMENT: str = "sandbox"
    AT_USERNAME: str = ""
    AT_API_KEY: str = ""
    # Registered alphanumeric sender name; empty uses the provider's shared short code.
    AT_SENDER_ID: str = ""
    # Secret path segment for delivery reports, which carry no signature.
    AT_CALLBACK_SECRET: str = ""

    # Uploaded files. "r2" = Cloudflare R2, "local" = a folder (development and
    # tests only), empty = uploads switched off.
    STORAGE_BACKEND: str = ""
    LOCAL_STORAGE_DIR: str = "uploads"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""

    @model_validator(mode="after")
    def _fail_closed(self):
        if self.ENVIRONMENT not in ENVIRONMENTS:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(ENVIRONMENTS)}")
        if not self.is_development:
            if len(self.JWT_SECRET_KEY) < MIN_SECRET_LENGTH:
                raise ValueError(f"JWT_SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters outside development")
            if self.PROXY_SHARED_SECRET and len(self.PROXY_SHARED_SECRET) < MIN_SECRET_LENGTH:
                raise ValueError(f"PROXY_SHARED_SECRET must be at least {MIN_SECRET_LENGTH} characters")
            if self.MPESA_CALLBACK_SECRET and len(self.MPESA_CALLBACK_SECRET) < MIN_SECRET_LENGTH:
                raise ValueError(f"MPESA_CALLBACK_SECRET must be at least {MIN_SECRET_LENGTH} characters")
            if self.AT_CALLBACK_SECRET and len(self.AT_CALLBACK_SECRET) < MIN_SECRET_LENGTH:
                raise ValueError(f"AT_CALLBACK_SECRET must be at least {MIN_SECRET_LENGTH} characters")
        if self.AT_ENVIRONMENT not in {"sandbox", "production"}:
            raise ValueError("AT_ENVIRONMENT must be sandbox or production")
        if self.MPESA_ENVIRONMENT not in {"sandbox", "production"}:
            raise ValueError("MPESA_ENVIRONMENT must be sandbox or production")
        if self.STORAGE_BACKEND not in {"", "r2", "local"}:
            raise ValueError("STORAGE_BACKEND must be r2, local or empty")
        if self.STORAGE_BACKEND == "local" and not self.is_development:
            raise ValueError("Local file storage is for development only; use r2")
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
