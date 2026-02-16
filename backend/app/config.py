from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class AppSettings(BaseSettings):
    # App
    app_env: str = Field(default="dev")
    database_url: str = Field(default="sqlite:///./data/trading.db")

    # Market/Brokers (placeholders for now)
    iol_username: Optional[str] = None
    iol_password: Optional[str] = None
    iol_base_url: str = Field(default="https://api.invertironline.com")

    rofex_env: str = Field(default="REMARKET")  # or LIVE
    rofex_username: Optional[str] = None
    rofex_password: Optional[str] = None
    rofex_account: Optional[str] = None

    ibkr_host: str = Field(default="127.0.0.1")
    ibkr_port: int = Field(default=7497)
    ibkr_client_id: int = Field(default=1)

    # Agent / RAG
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    gemini_model: str = Field(default="gemini-1.5-pro")
    chroma_path: str = Field(default="./data/chroma")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
