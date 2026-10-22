from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "FileFlow"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://fileflow:fileflow123@localhost:5432/fileflow"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "fileflow"
    minio_secure: bool = False

    jwt_secret: str = "your-super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    class Config:
        env_file = ".env"
        case_sensitive = False

    def model_post_init(self, __context):
        # Neon gives postgresql://... ?sslmode=require
        # asyncpg needs postgresql+asyncpg:// and ssl=require
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=require" in url:
            url = url.replace("sslmode=require", "ssl=require")
        self.database_url = url


@lru_cache()
def get_settings() -> Settings:
    return Settings()
