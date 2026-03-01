from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    gemini_api_key: str = Field(description="Google Gemini API key")
    gemini_model: str = Field(default="gemini-2.0-pro", description="Gemini model to use")
    notion_token: str = Field(description="Notion integration token")
    notion_database_id: str | None = Field(default=None, description="Explicit Notion database ID")
    token_budget: int = Field(default=1_000_000, description="Max tokens per daily run")
    log_level: str = Field(default="INFO")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def load_settings() -> Settings:
    return Settings()
