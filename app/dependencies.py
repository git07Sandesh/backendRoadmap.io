# app/dependencies.py
from supabase import create_client, Client
from fastapi import HTTPException
import spacy

# Assuming config.py is in the same directory or adjust import accordingly
from .config import settings

_supabase_client: Client = None
_nlp_model = None


def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not settings.supabase_url or not settings.supabase_key:
            raise HTTPException(
                status_code=500,
                detail="Supabase URL or Key not configured in .env file",
            )
        try:
            _supabase_client = create_client(
                settings.supabase_url, settings.supabase_key
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Supabase client: {str(e)}",
            )
    return _supabase_client


def get_nlp_model():
    global _nlp_model
    if _nlp_model is None:
        try:
            _nlp_model = spacy.load(settings.spacy_model)
        except OSError:
            print(f"spaCy model '{settings.spacy_model}' not found. Downloading...")
            try:
                spacy.cli.download(settings.spacy_model)
                _nlp_model = spacy.load(settings.spacy_model)
            except Exception as e:
                print(
                    f"Failed to download or load spaCy model '{settings.spacy_model}': {e}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"spaCy model '{settings.spacy_model}' not found or failed to download.",
                )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to load spaCy model: {str(e)}"
            )
    return _nlp_model
