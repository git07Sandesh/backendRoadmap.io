from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Union
import yake
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

# === Supabase Client ===
supabase = create_client(os.getenv("supabase_url"), os.getenv("supabase_key"))

# === YAKE Keyword Extractor ===
kw_extractor = yake.KeywordExtractor(lan="en", n=3, top=5, dedupLim=0.7)

# === Pydantic Models ===
class FeaturedSkill(BaseModel):
    skill: str
    rating: int

class ResumeInput(BaseModel):
    profile: Dict[str, Union[str, None]]
    workExperiences: List[Dict[str, Union[str, List[str]]]]
    educations: List[Dict[str, Union[str, List[str]]]]
    projects: List[Dict[str, Union[str, List[str]]]]
    skills: Dict[str, Union[List[str], List[FeaturedSkill]]]
    custom: Dict[str, Union[str, List[str], None]]

class TaggedItem(BaseModel):
    title: str
    tags: List[str]


import google.generativeai as genai

# Initialize Gemini client
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
embedding_model = genai.get_model("models/embedding-001")

def get_embedding(text: str) -> list[float]:
    try:
        response = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
            title="Resume Tags"
        )
        return response["embedding"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")


# === Main Endpoint ===
@router.post("/auto-job-predict")
def auto_tag_and_predict(resume: ResumeInput):
    tag_output = {
        "profile": [],
        "projects": [],
        "skills": [],
        "educations": [],
        "workExperiences": [],
        "custom": []
    }

    def extract_from_text(text: str) -> List[str]:
        if not text or not isinstance(text, str):
            return []
        return [kw[0] for kw in kw_extractor.extract_keywords(text)]

    if resume.profile:
        tag_output["profile"].extend(extract_from_text(resume.profile.get("summary", "")))

    for proj in resume.projects:
        tags = extract_from_text(proj.get("project", ""))
        tag_output["projects"].append({"title": proj.get("project", "Untitled"), "tags": tags})

    for work in resume.workExperiences:
        tags = extract_from_text(work.get("jobTitle", ""))
        tag_output["workExperiences"].append({"title": work.get("jobTitle", "Untitled"), "tags": tags})

    for edu in resume.educations:
        tags = extract_from_text(edu.get("degree", ""))
        tag_output["educations"].append({"title": edu.get("degree", "Untitled"), "tags": tags})

    for desc in resume.skills.get("descriptions", []):
        tag_output["skills"].extend(extract_from_text(desc))

    if resume.custom:
        for k, v in resume.custom.items():
            if isinstance(v, str):
                tag_output["custom"].extend(extract_from_text(v))
            elif isinstance(v, list):
                for item in v:
                    tag_output["custom"].extend(extract_from_text(item))

    # === Flatten Tags ===
    flat_tags = list(set([
        *tag_output["profile"],
        *tag_output["skills"],
        *[t for item in tag_output["projects"] for t in item["tags"]],
        *[t for item in tag_output["workExperiences"] for t in item["tags"]],
        *[t for item in tag_output["educations"] for t in item["tags"]],
        *tag_output["custom"]
    ]))

    if not flat_tags:
        raise HTTPException(status_code=400, detail="No tags extracted from resume.")

    # === Supabase Vector Matching ===
    tag_text = " ".join(flat_tags)
    embedding_vector = get_embedding(tag_text)

    try:
        embedding_response = supabase.rpc("match_jobs_from_text", {
            "input_embedding": embedding_vector,
            "top_k": 300
        }).execute()
        matched_jobs = embedding_response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

        
    return {
        "tags_by_section": tag_output,
        "flattened_tags": flat_tags,
        "job_logits": matched_jobs
    }
