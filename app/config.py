from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Last Mile Platform"
    secret_key: str = "change-me-later"
    prototype_label: str = "PROTOTYPE - mock data only"
    database_url: str = "sqlite:///./lastmile.db"
    mock_base_url: str = "http://localhost:8000/mock"


settings = Settings()