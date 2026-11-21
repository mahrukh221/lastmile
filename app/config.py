from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Last Mile Platform"
    secret_key: str = "dev-only-secret-change-me-in-the-env-file-0123456789"
    access_token_minutes: int = 60
    prototype_label: str = "PROTOTYPE - mock data only"
    database_url: str = "sqlite:///./lastmile.db"
    mock_base_url: str = "http://localhost:8000/mock"


settings = Settings()