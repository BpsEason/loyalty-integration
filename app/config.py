from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    laravel_api_base_url: str = "http://localhost:8088/api/v1"
    laravel_email: str | None = None
    laravel_password: str | None = None
    laravel_coffee_email: str | None = None
    laravel_coffee_password: str | None = None
    laravel_coffee_campaign_reward_id: int = 1

    default_timeout: float = 30.0


settings = Settings()