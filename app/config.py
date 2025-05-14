from pydantic_settings import BaseSettings
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    # Add any other configurations here, e.g., for spaCy model
    spacy_model: str = "en_core_web_sm"

    class Config:
        env_file = "../.env"  # .env file is in the parent directory (project root)
        env_file_encoding = "utf-8"


settings = Settings()
