from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str
    anthropic_api_key: str = ""
    api_key: str = "changeme"
    app_env: str = "development"
    app_version: str = "0.1.0"


settings = Settings()
