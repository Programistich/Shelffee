from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    webapp_url: str
    database_url: str = "postgresql+asyncpg://shelffee:shelffee@db:5432/shelffee"
    web_host: str = "0.0.0.0"
    web_port: int = 8080


settings = Settings()
