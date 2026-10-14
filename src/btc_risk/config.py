from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    database_url: str = "postgresql://btc:btc@localhost:5433/btc_risk"
    data_dir: Path = Field(default=Path("data"))
    mempool_base_url: str = "https://mempool.space/api"

    @property
    def sdn_path(self) -> Path:
        return self.data_dir / "sdn.xml"

    @property
    def chain_cache_path(self) -> Path:
        return self.data_dir / "chain_cache.sqlite"

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)


def get_settings() -> Settings:
    return Settings()
