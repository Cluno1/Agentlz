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

    # database (只做添加，允许 .env 中的 DB_* 键被识别)
    db_host: str | None = Field(default=None, env="DB_HOST")
    db_port: int | None = Field(default=None, env="DB_PORT")
    db_user: str | None = Field(default=None, env="DB_USER")
    db_password: str | None = Field(default=None, env="DB_PASSWORD")
    db_name: str | None = Field(default=None, env="DB_NAME")
    # 用户管理表名 & 多租户请求头
    user_table_name: str = Field(default="users", env="USER_TABLE_NAME")
    tenant_id_header: str = Field(default="X-Tenant-ID", env="TENANT_ID_HEADER")
    # JWT token 配置
    auth_jwt_secret: str = Field(default="dev-secret", env="AUTH_JWT_SECRET")
    auth_jwt_alg: str = Field(default="HS256", env="AUTH_JWT_ALG")
    auth_jwt_issuer: str = Field(default="agentlz", env="AUTH_JWT_ISSUER")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    # 配置HuggingFace 中文句向量嵌入模型
    hf_embedding_model: str = Field(default="BAAI/bge-small-zh-v1.5", env="HF_EMBEDDING_MODEL")

def get_settings() -> Settings:
    return Settings()

