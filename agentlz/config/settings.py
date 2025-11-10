# Settings 类与 get_settings 函数
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables (.env supported)."""

    # 自定义api
    chatopenai_api_key: str | None = Field(default=None, env="CHATOPENAI_API_KEY")
    chatopenai_base_url: str = Field(default=None, env="CHATOPENAI_BASE_URL")
    # openai 官方api
    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")
    # mail
    email_address: str | None = Field(default=None, env="EMAIL_ADDRESS")
    email_password: str | None = Field(default=None, env="EMAIL_PASSWORD")
    smtp_host: str = Field(default="smtp.163.com", env="SMTP_HOST")
    smtp_ssl_port: int = Field(default=465, env="SMTP_SSL_PORT")
    imap_host: str = Field(default="imap.163.com", env="IMAP_HOST")
    # model
    model_name: str = Field(default=None, env="MODEL_NAME")
    model_temperature: float = Field(default=0.0, env="MODEL_TEMPERATURE")
    system_prompt: str = Field(default="You are a helpful assistant.", env="SYSTEM_PROMPT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    # search
    bing_api_key: str | None = Field(default=None, env="BING_API_KEY")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    return Settings()