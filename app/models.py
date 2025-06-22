from typing import List, Optional, Union, Dict
from pydantic import BaseModel, Field


class ResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    url: str = ""
    summary: str = ""
    location: str = ""


class ResumeWorkExperience(BaseModel):
    company: str = ""
    job_title: str = Field(alias="jobTitle", default="")  # For matching original JSON
    date: str = ""
    descriptions: List[str] = []


class ResumeEducation(BaseModel):
    school: str = ""
    degree: str = ""
    date: str = ""
    gpa: str = ""
    descriptions: List[str] = []


class ResumeProject(BaseModel):
    project: str = ""
    date: str = ""
    descriptions: List[str] = []


class FeaturedSkill(BaseModel):
    skill: str = ""
    rating: int = 4  # Default from original


class ResumeSkills(BaseModel):
    featured_skills: List[FeaturedSkill] = Field(
        alias="featuredSkills",
        default_factory=lambda: [FeaturedSkill() for _ in range(6)],
    )
    descriptions: List[str] = []


class ResumeCustom(BaseModel):
    descriptions: List[str] = []


class Resume(BaseModel):
    profile: ResumeProfile = Field(default_factory=ResumeProfile)
    work_experiences: List[ResumeWorkExperience] = Field(
        alias="workExperiences", default_factory=list
    )
    educations: List[ResumeEducation] = Field(default_factory=list)
    projects: List[ResumeProject] = Field(default_factory=list)
    skills: ResumeSkills = Field(default_factory=ResumeSkills)
    custom: Dict[str, ResumeCustom] = Field(default_factory=dict)

    class Config:
        populate_by_name = True  # Allows using job_title and featured_skills


# For internal parser types
class TextItem(BaseModel):
    text: str
    x: float
    y: float
    width: float
    height: float
    font_name: str = Field(alias="fontName")
    # hasEOL is tricky with PyMuPDF. We'll primarily use coordinates.
    # We can try to infer it if needed, or adapt logic.
    # For now, let's assume line grouping logic handles it.
    # has_eol: bool = Field(alias="hasEOL", default=False)

    class Config:
        populate_by_name = True


Line = List[TextItem]
Lines = List[Line]

ResumeKey = Union[str]  # Simplified from original, essentially section names


class ResumeSectionToLines(BaseModel):
    profile: Optional[Lines] = None
    education: Optional[Lines] = None
    work_experience: Optional[Lines] = Field(alias="workExperience", default=None)
    project: Optional[Lines] = None
    skill: Optional[Lines] = None
    # For other dynamic sections
    # This can be handled by allowing extra fields in Pydantic or a Dict field
    other_sections: Dict[str, Lines] = Field(default_factory=dict)


Subsections = List[Lines]


# FeatureSet and TextScore related types
class TextScore(BaseModel):
    text: str
    score: int
    match: bool


TextScores = List[TextScore]
# FeatureSet will be represented as tuples in Python:
# [(callable, score)] or [(callable_returning_match_obj, score, return_matching_text_only_bool)]


# Pydantic model for the learning question request
class LearningQuestionRequest(BaseModel):
    prompt: str
    prompt: str


class JobMatchInput(BaseModel):
    tags: List[str]
    top_k: int = 5  # Optional, default top 5 jobs


# New models for user resume storage
class UserResumeData(BaseModel):
    user_id: str
    resume: Resume


class UserResumeStorage(BaseModel):
    user_id: str
    resume_data: dict
    education_embedding: Optional[List[float]] = None
    work_experience_embedding: Optional[List[float]] = None
    projects_embedding: Optional[List[float]] = None
    skills_embedding: Optional[List[float]] = None
    full_resume_embedding: Optional[List[float]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ResumeStorageResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    embeddings_generated: Dict[str, bool]


# New models for structured user resume storage
class StructuredUserResumeStorage(BaseModel):
    user_id: str
    # Profile data
    profile_name: Optional[str] = None
    profile_email: Optional[str] = None
    profile_phone: Optional[str] = None
    profile_url: Optional[str] = None
    profile_summary: Optional[str] = None
    profile_location: Optional[str] = None

    # Structured data as JSON columns
    work_experiences: Optional[List[dict]] = None
    educations: Optional[List[dict]] = None
    projects: Optional[List[dict]] = None
    skills: Optional[dict] = None
    custom: Optional[dict] = None

    # Embeddings
    education_embedding: Optional[List[float]] = None
    work_experience_embedding: Optional[List[float]] = None
    projects_embedding: Optional[List[float]] = None
    skills_embedding: Optional[List[float]] = None
    full_resume_embedding: Optional[List[float]] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class StructuredResumeStorageResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    embeddings_generated: Dict[str, bool]
    data_id: Optional[str] = None
