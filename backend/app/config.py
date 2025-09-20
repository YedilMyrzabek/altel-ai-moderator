from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    # Supabase (используем service key на сервере)
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")  # важное: service key!

    # YouTube
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY")

    # Instagram
    instagram_username: str = os.getenv("INSTAGRAM_USERNAME", "")
    instagram_password: str = os.getenv("INSTAGRAM_PASSWORD", "")

    # ML Service
    ml_service_url: str = "http://localhost:5000"

    # App
    debug: bool = os.getenv("DEBUG", "True") == "True"

    class Config:
        env_file = ".env"


settings = Settings()