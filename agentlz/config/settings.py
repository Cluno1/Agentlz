# Settings 类与 get_settings 函数
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables (.env supported)."""

    # redis
    redis_host: str = Field(default=None, env="REDIS_HOST")
    redis_port: int = Field(default=None, env="REDIS_PORT")
    redis_db: int = Field(default=None, env="REDIS_DB")
    redis_password: str | None = Field(default=None, env="REDIS_PASSWORD")
    redis_url: str | None = Field(default=None, env="REDIS_URL")
    # rabbitmq
    rabbitmq_host: str = Field(default=None, env="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=None, env="RABBITMQ_PORT")
    rabbitmq_user: str = Field(default=None, env="RABBITMQ_USER")
    rabbitmq_password: str = Field(default=None, env="RABBITMQ_PASSWORD")
    rabbitmq_vhost: str = Field(default=None, env="RABBITMQ_VHOST")
    rabbitmq_url: str = Field(default=None, env="RABBITMQ_URL")
    rabbitmq_management_url: str = Field(
        default=None, env="RABBITMQ_MANAGEMENT_URL")

    # cos 对象存储
    cos_bucket: str = Field(default=None, env="COS_BUCKET")
    cos_secret_id: str = Field(default=None, env="COS_SECRET_ID")
    cos_secret_key: str = Field(default=None, env="COS_SECRET_KEY")
    cos_region: str = Field(default=None, env="COS_REGION")
    cos_base_url: str = Field(default=None, env="COS_BASE_URL")

    # 自定义api
    chatopenai_api_key: str | None = Field(
        default=None, env="CHATOPENAI_API_KEY")
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
    system_prompt: str = Field(
        default="You are a helpful assistant.", env="SYSTEM_PROMPT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    # search
    bing_api_key: str | None = Field(default=None, env="BING_API_KEY")

    # database (只做添加，允许 .env 中的 DB_* 键被识别)
    db_host: str | None = Field(default=None, env="DB_HOST")
    db_port: int | None = Field(default=None, env="DB_PORT")
    db_user: str | None = Field(default=None, env="DB_USER")
    db_password: str | None = Field(default=None, env="DB_PASSWORD")
    db_name: str | None = Field(default=None, env="DB_NAME")
    # 向量数据库（pgvector）
    vector_backend: str | None = Field(default=None, env="VECTOR_BACKEND")
    pgvector_host: str | None = Field(default=None, env="PGVECTOR_HOST")
    pgvector_port: int | None = Field(default=None, env="PGVECTOR_PORT")
    pgvector_db: str | None = Field(default=None, env="PGVECTOR_DB")
    pgvector_user: str | None = Field(default=None, env="PGVECTOR_USER")
    pgvector_password: str | None = Field(
        default=None, env="PGVECTOR_PASSWORD")
    pgvector_url: str | None = Field(default=None, env="PGVECTOR_URL")
    #  多租户请求头
    tenant_id_header: str = Field(
        default="X-Tenant-ID", env="TENANT_ID_HEADER")
    # JWT token 配置
    auth_jwt_secret: str = Field(default="dev-secret", env="AUTH_JWT_SECRET")
    auth_jwt_alg: str = Field(default="HS256", env="AUTH_JWT_ALG")
    auth_jwt_issuer: str = Field(default="agentlz", env="AUTH_JWT_ISSUER")
    # CORS
    cors_allow_origins: list[str] = Field(
        default=["*"], env="CORS_ALLOW_ORIGINS")
    cors_allow_credentials: bool = Field(
        default=True, env="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(
        default=["*"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: list[str] = Field(
        default=["*"], env="CORS_ALLOW_HEADERS")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8")
    # 配置HuggingFace 中文句向量嵌入模型
    hf_embedding_model: str = Field(
        default="BAAI/bge-small-zh-v1.5", env="HF_EMBEDDING_MODEL")

    # sql 表名称
    user_table_name: str = Field(default="users", env="USER_TABLE_NAME")
    document_table_name: str = Field(
        default="document", env="DOCUMENT_TABLE_NAME")
    tenant_table_name: str = Field(
        default="tenant", env="TENANT_TABLE_NAME")
    user_doc_permission_table_name: str = Field(
        default="user_doc_permission", env="USER_DOC_PERMISSION_TABLE_NAME")

    # MCP 混合检索参数（语义/可信度融合）
    # alpha：语义权重；theta：语义门槛；N：语义召回 Top-N；k：最终返回 Top-k
    mcp_search_alpha: float = Field(default=0.7, env="MCP_SEARCH_ALPHA")
    mcp_search_theta: float = Field(default=0.75, env="MCP_SEARCH_THETA")
    mcp_search_topn: int = Field(default=50, env="MCP_SEARCH_TOPN")
    mcp_search_topk: int = Field(default=5, env="MCP_SEARCH_TOPK")

    # MCP 可信度更新参数
    mcp_trust_update_alpha: float = Field(default=0.2, env="MCP_TRUST_UPDATE_ALPHA")
    mcp_trust_error_cap: int = Field(default=30, env="MCP_TRUST_ERROR_CAP")
    mcp_trust_skip_cap: int = Field(default=60, env="MCP_TRUST_SKIP_CAP")

    # 事件壳版本
    event_schema_version: str = Field(default="v1", env="EVENT_SCHEMA_VERSION")

    chain_hard_limit: int = Field(default=20, env="CHAIN_HARD_LIMIT")


def get_settings() -> Settings:
    return Settings()
