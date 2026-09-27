from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    webapp_url: str
    database_url: str = "postgresql+asyncpg://shelffee:shelffee@db:5432/shelffee"
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    openai_api_key: str
    openai_model: str = "gpt-5.4"
    openai_base_url: str | None = None


settings = Settings()
