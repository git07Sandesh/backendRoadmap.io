from supabase import create_client, Client
from fastapi import HTTPException

# Assuming config.py is in the same directory or adjust import accordingly
from .config import settings

_supabase_client: Client = None


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
