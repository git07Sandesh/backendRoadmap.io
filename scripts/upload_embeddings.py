import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from supabase import create_client
from app.data.job_description import JOB_DESCRIPTIONS
import google.generativeai as genai

load_dotenv()
supabase = create_client(os.getenv("supabase_url"), os.getenv("supabase_key"))

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_embedding(text: str) -> list:
    response = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="RETRIEVAL_DOCUMENT",
        title="Job Description"
    )
    return response["embedding"]

# === Upload Gemini embeddings to Supabase ===
for title, desc in JOB_DESCRIPTIONS.items():
    emb = get_embedding(desc)
    res = supabase.table("job_embeddings").upsert({
        "job_title": title,
        "description": desc,
        "embedding": emb
    }).execute()
    print(f"✅ {title}" if res.data else f"❌ {title} — {res}")
