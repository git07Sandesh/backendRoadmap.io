from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Union
import torch
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim
from keybert import KeyBERT
from app.data.job_description import JOB_DESCRIPTIONS


router = APIRouter()

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
kw_model = KeyBERT(model=embedding_model)

# Job description corpus

job_titles = list(JOB_DESCRIPTIONS.keys())
job_texts = list(JOB_DESCRIPTIONS.values())
job_embeddings = embedding_model.encode(job_texts, convert_to_tensor=True)

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

class TagStructureInput(BaseModel):
    profile: List[str] = []
    skills: List[str] = []
    projects: List[TaggedItem] = []
    workExperiences: List[TaggedItem] = []
    educations: List[TaggedItem] = []
    custom: List[str] = []

class JobMatchInput(BaseModel):
    tags: List[str]
    top_k: int = 3

@router.post("/auto-job-predict")
def auto_tag_and_predict(resume: ResumeInput):
    # === Step 1: Extract Tags === #
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
        keywords = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            top_n=5
        )
        return [kw[0] for kw in keywords]

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

    # === Step 2: Flatten Tags === #
    flat_tags = []
    flat_tags.extend(tag_output["profile"])
    flat_tags.extend(tag_output["skills"])
    for group in ["projects", "workExperiences", "educations"]:
        for item in tag_output[group]:
            flat_tags.extend(item.get("tags", []))
    flat_tags.extend(tag_output["custom"])
    flat_tags = list(set(tag for tag in flat_tags if tag.strip()))

    # === Step 3: Predict Jobs === #
    if not flat_tags:
        raise HTTPException(status_code=400, detail="No tags extracted from resume.")

    tag_text = " ".join(flat_tags)
    tag_embedding = embedding_model.encode(tag_text, convert_to_tensor=True)
    similarities = cos_sim(tag_embedding, job_embeddings)[0]

    top_k = 300
    top_indices = torch.topk(similarities, k=top_k).indices.tolist()
    job_logits = {
        job_titles[i]: float(similarities[i])
        for i in top_indices
    }

    return {
        "tags_by_section": tag_output,
        "flattened_tags": flat_tags,
        "job_logits": job_logits
    }
