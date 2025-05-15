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
        alias="workExperiences", default_factory=lambda: [ResumeWorkExperience()]
    )
    educations: List[ResumeEducation] = Field(
        default_factory=lambda: [ResumeEducation()]
    )
    projects: List[ResumeProject] = Field(default_factory=lambda: [ResumeProject()])
    skills: ResumeSkills = Field(default_factory=ResumeSkills)
    custom: ResumeCustom = Field(default_factory=ResumeCustom)

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
