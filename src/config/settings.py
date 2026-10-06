from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    laravel_api_base_url: str
    laravel_email: str
    laravel_password: str
    laravel_coffee_email: str
    laravel_coffee_password: str
    laravel_coffee_campaign_reward_id: int

    # Reverb WebSocket settings - 與Laravel .env設定完全一致
    reverb_app_id: str
    reverb_app_key: str
    reverb_app_secret: str
    reverb_host: str
    reverb_port: int
    reverb_scheme: str
    reverb_auth_endpoint: str

    default_timeout: float = 30.0


settings = Settings()