"""Database configuration and FastAPI dependencies."""

from collections.abc import AsyncGenerator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Settings(BaseSettings):
    """API configuration via Pydantic Settings."""

    postgres_user: str = "homepedia"
    postgres_password: str = "homepedia_secret"
    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_db: str = "homepedia"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency: provides an async SQLAlchemy session."""
    async with async_session() as session:
        yield session
