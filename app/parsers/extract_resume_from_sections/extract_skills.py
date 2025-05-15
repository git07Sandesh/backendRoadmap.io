from typing import Tuple, List
from app.parsers.types import ResumeSectionToLinesMap
from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
)
from app.models import ResumeSkills, FeaturedSkill  # For return type
from app.utils import (
    deep_clone,
)  # If needed for initialFeaturedSkills, or manual creation


# Recreate initialFeaturedSkills as per original Redux slice
def get_initial_featured_skills() -> List[FeaturedSkill]:
    return [FeaturedSkill(skill="", rating=4) for _ in range(6)]


def extract_skills(
    sections: ResumeSectionToLinesMap,
) -> Tuple[ResumeSkills, None]:  # No scores for skills in original
    skill_lines = get_section_lines_by_keywords(
        sections, ["skill", "technologies", "competencies"]
    )

    raw_desc_line_idx = get_descriptions_line_idx(skill_lines)
    # Default to 0 if no bullet points found, as per original TS logic (?? 0)
    descriptions_line_idx = raw_desc_line_idx if raw_desc_line_idx is not None else 0

    descriptions: List[str] = []
    if descriptions_line_idx <= len(skill_lines):  # Ensure index is valid
        desc_lines_to_process = skill_lines[descriptions_line_idx:]
        if desc_lines_to_process:
            descriptions = get_bullet_points_from_lines(desc_lines_to_process)

    featured_skills = get_initial_featured_skills()  # Creates a new list each time

    # Original uses slice(0, descriptionsLineIdx) for featured skills lines.
    # This means if descriptions_line_idx is 0, featured_skills_lines will be empty.
    if descriptions_line_idx > 0 and descriptions_line_idx <= len(skill_lines):
        featured_skills_lines = skill_lines[:descriptions_line_idx]
        featured_skills_text_items = [
            item
            for sublist in featured_skills_lines
            for item in sublist
            if item.text.strip()
        ][
            :6
        ]  # Max 6 featured skills

        for i, text_item in enumerate(featured_skills_text_items):
            if i < len(featured_skills):  # Ensure we don't go out of bounds
                featured_skills[i].skill = text_item.text.strip()
                # Rating remains default unless logic is added to parse it

    skills_data = ResumeSkills(
        featuredSkills=featured_skills, descriptions=descriptions
    )
    return skills_data, None  # No scores returned for skills
