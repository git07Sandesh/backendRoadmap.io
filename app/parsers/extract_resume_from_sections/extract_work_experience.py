import re
from typing import List, Tuple, Dict
from app.parsers.types import TextItem, FeatureSets, ResumeSectionToLinesMap, TextScores
from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.parsers.extract_resume_from_sections.lib.subsections import (
    divide_section_into_subsections,
)
from app.parsers.extract_resume_from_sections.lib.common_features import (
    DATE_FEATURE_SETS,
    has_number,
    get_has_text,
    is_bold,
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
)
from app.models import ResumeWorkExperience  # For return type

WORK_EXPERIENCE_KEYWORDS_LOWERCASE = [
    "work",
    "experience",
    "employment",
    "history",
    "job",
    "career",
]
JOB_TITLES = [
    "Accountant",
    "Administrator",
    "Advisor",
    "Agent",
    "Analyst",
    "Apprentice",
    "Architect",
    "Assistant",
    "Associate",
    "Auditor",
    "Bartender",
    "Biologist",
    "Bookkeeper",
    "Buyer",
    "Carpenter",
    "Cashier",
    "CEO",
    "Clerk",
    "Co-op",
    "Co-Founder",
    "Consultant",
    "Coordinator",
    "CTO",
    "Developer",
    "Designer",
    "Director",
    "Driver",
    "Editor",
    "Electrician",
    "Engineer",
    "Extern",
    "Founder",
    "Freelancer",
    "Head",
    "Intern",
    "Janitor",
    "Journalist",
    "Laborer",
    "Lawyer",
    "Lead",
    "Manager",
    "Mechanic",
    "Member",
    "Nurse",
    "Officer",
    "Operator",
    "Operation",
    "Photographer",
    "President",
    "Producer",
    "Recruiter",
    "Representative",
    "Researcher",
    "Sales",
    "Server",
    "Scientist",
    "Specialist",
    "Supervisor",
    "Teacher",
    "Technician",
    "Trader",
    "Trainee",
    "Treasurer",
    "Tutor",
    "Vice",
    "VP",
    "Volunteer",
    "Webmaster",
    "Worker",
    "Software Engineer",
    "Data Scientist",
    "Product Manager",  # Added some common tech roles
]
JOB_TITLES_LOWER = {title.lower() for title in JOB_TITLES}


def has_job_title(item: TextItem) -> bool:
    # Check for full phrase job titles first (e.g. "Software Engineer")
    text_lower = item.text.lower()
    for job_title_phrase in JOB_TITLES_LOWER:
        if len(job_title_phrase.split()) > 1 and job_title_phrase in text_lower:
            return True
    # Then check for single word job titles
    return any(word.lower() in JOB_TITLES_LOWER for word in item.text.split())


def has_more_than_5_words(item: TextItem) -> bool:
    return len(item.text.split()) > 5


JOB_TITLE_FEATURE_SET: FeatureSets = [
    (has_job_title, 4),
    (has_number, -4),
    (has_more_than_5_words, -2),
]


def extract_work_experience(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeWorkExperience], List[Dict[str, TextScores]]]:
    work_experiences_data: List[ResumeWorkExperience] = []
    work_experiences_scores_debug: List[Dict[str, TextScores]] = []

    work_lines = get_section_lines_by_keywords(
        sections, WORK_EXPERIENCE_KEYWORDS_LOWERCASE
    )
    subsections = divide_section_into_subsections(work_lines)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue

        # Default descriptionsLineIdx to 2 as per original.
        # If subsection_lines has < 2 lines, this needs care.
        # get_descriptions_line_idx can return None.
        raw_desc_line_idx = get_descriptions_line_idx(subsection_lines)
        descriptions_line_idx = (
            raw_desc_line_idx
            if raw_desc_line_idx is not None
            else (2 if len(subsection_lines) > 2 else len(subsection_lines))
        )

        # Ensure subsectionInfoTextItems doesn't go out of bounds
        slice_end_idx = min(descriptions_line_idx, len(subsection_lines))
        subsection_info_text_items = [
            item for sublist in subsection_lines[:slice_end_idx] for item in sublist
        ]

        date, date_scores = get_text_with_highest_feature_score(
            subsection_info_text_items, DATE_FEATURE_SETS
        )
        job_title, job_title_scores = get_text_with_highest_feature_score(
            subsection_info_text_items, JOB_TITLE_FEATURE_SET
        )

        # COMPANY_FEATURE_SET dynamically uses get_has_text with extracted date and jobTitle
        company_feature_set: FeatureSets = [
            (is_bold, 2),
            (get_has_text(date), -4),  # Text from 'date' variable
            (get_has_text(job_title), -4),  # Text from 'job_title' variable
        ]
        company, company_scores = get_text_with_highest_feature_score(
            subsection_info_text_items,
            company_feature_set,
            False,  # Allow negative high score
        )

        descriptions: List[str] = []
        if descriptions_line_idx < len(
            subsection_lines
        ):  # Ensure there are lines for description
            desc_lines_to_process = subsection_lines[descriptions_line_idx:]
            if desc_lines_to_process:
                descriptions = get_bullet_points_from_lines(desc_lines_to_process)

        work_experiences_data.append(
            ResumeWorkExperience(
                company=company,
                jobTitle=job_title,
                date=date,
                descriptions=descriptions,
            )
        )
        work_experiences_scores_debug.append(
            {
                "company": company_scores,
                "jobTitle": job_title_scores,
                "date": date_scores,
            }
        )

    return work_experiences_data, work_experiences_scores_debug
