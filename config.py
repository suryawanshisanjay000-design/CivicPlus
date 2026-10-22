
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    
    # App
    app_name: str = "CivicPulse"
    environment: str = "development"
    debug: bool = True
    port: int = 8000
    
    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    
    # AI (optional)
    groq_api_key: str | None = None
    
    # Auth
    secret_key: str = "dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Required Supabase vars are provided via environment on Render/CI, not statically knowable.
settings = Settings()  # type: ignore[call-arg]