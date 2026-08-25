"""Application configuration via Pydantic Settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Gemini & OpenAI
    gemini_api_key: str = ""
    openai_api_key: str = ""

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "f1_context"
    postgres_user: str = "postgres"
    postgres_password: str

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_username: str = ""
    neo4j_password: str = "f1password"
    neo4j_database: str = "neo4j"
    aura_instanceid: str = ""
    aura_instancename: str = ""

    @property
    def active_neo4j_user(self) -> str:
        return self.neo4j_username or self.neo4j_user or "neo4j"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # FastF1
    fastf1_cache_dir: str = "./data/fastf1_cache"

    # App
    app_name: str = "F1 Context Graph AI"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
