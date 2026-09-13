from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str = "redis://localhost:6379/0"
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    RESEND_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "onboarding@resend.dev"
    FRONTEND_BASE_URL: str = "http://localhost:5173"

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