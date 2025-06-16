from app.parsers.types import ResumeSectionToLinesMap
from app.models import Resume, ResumeCustom  # Pydantic models
from app.parsers.extract_resume_from_sections.extract_profile import extract_profile
from app.parsers.extract_resume_from_sections.extract_education import extract_education
from app.parsers.extract_resume_from_sections.extract_work_experience import (
    extract_work_experience,
)
from app.parsers.extract_resume_from_sections.extract_project import extract_project
from app.parsers.extract_resume_from_sections.extract_skills import extract_skills

# Import debug score types if you want to include them in the final output
# from app.parsers.types import TextScores
# from typing import Dict, List


def extract_resume_from_sections(sections: ResumeSectionToLinesMap) -> Resume:
    profile_data, _profile_scores = extract_profile(sections)
    educations_data, _educations_scores = extract_education(sections)
    work_experiences_data, _work_experiences_scores = extract_work_experience(sections)
    projects_data, _projects_scores = extract_project(sections)
    skills_data, _skills_scores = extract_skills(
        sections
    )  # Skills extractor returns None for scores

    # For debugging, you could collect all scores and add them to a special field in Resume model
    # debug_scores = {
    #     "profile": _profile_scores,
    #     "educations": _educations_scores,
    #     # ... etc
    # }

    return Resume(
        profile=profile_data,
        educations=educations_data,
        workExperiences=work_experiences_data,  # Alias handled by Pydantic
        projects=projects_data,
        skills=skills_data,
        custom={},  # Empty dictionary as custom expects Dict[str, ResumeCustom]
    )
