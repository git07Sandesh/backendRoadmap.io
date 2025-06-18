from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from app.services.roadmap_prompt import build_prompt
from app.services.gemini_service import generate_roadmap_from_gemini

router = APIRouter()

class RoadmapRequest(BaseModel):
    resumeData: Dict
    flattenedTags: List[str]
    job: Dict

@router.post("/roadmap")
async def generate_roadmap(req: RoadmapRequest):
    prompt = build_prompt(req.resumeData, req.flattenedTags, req.job)
    roadmap = await generate_roadmap_from_gemini(prompt)
    return { "roadmap": roadmap }
