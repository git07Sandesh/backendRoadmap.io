# app/models/resume.py
from pydantic import BaseModel
from typing import Optional, List


class ResumeData(BaseModel):
    raw_text: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: List[str] = []
    experience: List[dict] = []
    education: List[dict] = []
