from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Union
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

router = APIRouter()

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
kw_model = KeyBERT(model=embedding_model)

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

@router.post("/tag-extract")
def extract_tags(resume: ResumeInput):
    tag_output = {
        "profile": [],
        "projects": [],
        "skills": [],
        "educations": [],
        "workExperiences": [],
        "custom": []
    }

    # Helper: extract tags from text
    def extract_from_text(text: str) -> List[str]:
        if not text or not isinstance(text, str):
            return []
        keywords = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            top_n=5
        )
        return [kw[0] for kw in keywords]

    # Profile
    if resume.profile:
        summary_tags = extract_from_text(resume.profile.get("summary", ""))
        tag_output["profile"].extend(summary_tags)

    # Projects
    for proj in resume.projects:
        tags = extract_from_text(proj.get("project", ""))
        tag_output["projects"].append({"title": proj.get("project", "Untitled"), "tags": tags})

    # Work Experiences
    for work in resume.workExperiences:
        tags = extract_from_text(work.get("position", ""))
        tag_output["workExperiences"].append({"title": work.get("position", "Untitled"), "tags": tags})

    # Educations
    for edu in resume.educations:
        tags = extract_from_text(edu.get("degree", ""))
        tag_output["educations"].append({"title": edu.get("degree", "Untitled"), "tags": tags})

    # Skills
    for desc in resume.skills.get("descriptions", []):
        tag_output["skills"].extend(extract_from_text(desc))

    # Custom
    if resume.custom:
        for k, v in resume.custom.items():
            if isinstance(v, str):
                tag_output["custom"].extend(extract_from_text(v))
            elif isinstance(v, list):
                for item in v:
                    tag_output["custom"].extend(extract_from_text(item))

    return tag_output
