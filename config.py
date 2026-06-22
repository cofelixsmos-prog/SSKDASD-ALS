from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./edutrack.db"
    SECRET_KEY: str = "changeme-use-a-random-32-char-string-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    GROQ_API_KEY: str = "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"
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    APP_NAME: str = "Scholarly"
    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
