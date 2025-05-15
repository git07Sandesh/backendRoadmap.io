import re
from typing import List, Tuple, Dict, Optional, Callable
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
    is_likely_tech_stack,
    has_season,
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
)
from app.models import ResumeWorkExperience

WORK_EXPERIENCE_KEYWORDS_LOWERCASE = [
    "work",
    "experience",
    "employment",
    "history",
    "job",
    "career",
    "professional experience",
    "research experience",
]
JOB_TITLES = [  # Keep this list comprehensive
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
    "Research Assistant",
    "Sales",
    "Server",
    "Scientist",
    "Specialist",
    "Supervisor",
    "Teacher",
    "Teaching Assistant",
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
    "Product Manager",
]
JOB_TITLES_LOWER = {title.lower() for title in JOB_TITLES}


def has_job_title(item: TextItem) -> bool:
    text_lower = item.text.lower()
    # Prioritize multi-word job titles from the list
    if any(
        jt_phrase in text_lower for jt_phrase in JOB_TITLES_LOWER if " " in jt_phrase
    ):
        return True
    # Check single words, but be careful they are not too generic
    # Only consider a single word a job title if it's in the list AND the text item isn't too long (suggesting it's part of a sentence)
    words = item.text.split()
    if len(words) <= 3:  # If the item has 3 words or less
        if any(word.lower() in JOB_TITLES_LOWER for word in words):
            return True
    return False


def has_more_than_N_words(n: int) -> Callable[[TextItem], bool]:
    return lambda item: len(item.text.split()) > n


# Stronger features for job titles
JOB_TITLE_FEATURE_SET: FeatureSets = [
    (has_job_title, 5),  # High positive score
    (is_bold, 2),  # Bold is a good indicator
    (
        has_number,
        -4,
    ),  # Job titles usually don't contain numbers (unless e.g. "Engineer III")
    (has_more_than_N_words(5), -3),  # Penalize very long strings
    (is_likely_tech_stack, -5),  # Job title is not a tech stack
]
# Features for company names
COMPANY_FEATURE_SETS: FeatureSets = [
    (is_bold, 1),  # Company names can be bold
    (has_job_title, -5),  # Company is not a job title
    (DATE_FEATURE_SETS[0][0], -3),  # Penalize if it looks like a year (part of date)
    (has_more_than_N_words(6), -2),  # Companies usually not extremely long sentences
    (is_likely_tech_stack, -4),
]


def extract_work_experience(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeWorkExperience], List[Dict[str, TextScores]]]:
    work_experiences_data: List[ResumeWorkExperience] = []
    work_experiences_scores_debug: List[Dict[str, TextScores]] = []

    # This includes "Research Experience" due to WORK_EXPERIENCE_KEYWORDS_LOWERCASE
    work_lines = get_section_lines_by_keywords(
        sections, WORK_EXPERIENCE_KEYWORDS_LOWERCASE
    )
    subsections = divide_section_into_subsections(work_lines)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue

        # First 1-2 lines are most likely to contain Job Title, Company, Date
        num_info_lines = min(2, len(subsection_lines))
        info_items = [
            item for sublist in subsection_lines[:num_info_lines] for item in sublist
        ]
        all_subsection_items = [
            item for sublist in subsection_lines for item in sublist
        ]  # For date

        job_title, job_title_scores = get_text_with_highest_feature_score(
            info_items, JOB_TITLE_FEATURE_SET
        )

        # Dynamically create COMPANY_FEATURE_SET to avoid matching already found job_title or date
        # This makes company extraction run after job_title and date are provisionally found.
        # For date, we'll extract it from all_subsection_items.
        date_candidate, date_scores_candidate = get_text_with_highest_feature_score(
            all_subsection_items, DATE_FEATURE_SETS
        )

        dynamic_company_feature_set: FeatureSets = [
            *COMPANY_FEATURE_SETS,  # Base features
            (
                (get_has_text(job_title), -5) if job_title else (lambda _: False, 0)
            ),  # Penalize matching job title
            (
                (get_has_text(date_candidate), -4)
                if date_candidate
                else (lambda _: False, 0)
            ),  # Penalize matching date
        ]
        company, company_scores = get_text_with_highest_feature_score(
            info_items,  # Search for company primarily in the top lines
            dynamic_company_feature_set,
            return_empty_string_if_highest_score_is_not_positive=False,  # Company can have low score
        )

        # Final date extraction based on the current subsection
        date, date_scores = get_text_with_highest_feature_score(
            all_subsection_items, DATE_FEATURE_SETS
        )

        descriptions: List[str] = []
        # Descriptions start after job title/company, or where bullets begin
        desc_line_idx_from_bullets = get_descriptions_line_idx(subsection_lines)

        # Heuristic for start of descriptions:
        # If bullets found, use that. Otherwise, assume after num_info_lines.
        start_desc_from_line_idx = (
            desc_line_idx_from_bullets
            if desc_line_idx_from_bullets is not None
            else num_info_lines
        )

        if start_desc_from_line_idx < len(subsection_lines):
            desc_lines_to_process = subsection_lines[start_desc_from_line_idx:]
            if desc_lines_to_process:
                descriptions = get_bullet_points_from_lines(desc_lines_to_process)

        # Clean up descriptions by removing company/job_title/date if they were accidentally included
        extracted_core_texts = {
            text for text in [company, job_title, date] if text and len(text) > 3
        }  # Min length to avoid removing "a", "in"
        cleaned_descriptions = []
        for desc in descriptions:
            is_core_text = False
            for core in extracted_core_texts:
                if (
                    core.lower() in desc.lower()
                ):  # Check if core text is part of description
                    is_core_text = True
                    break
            if not is_core_text:
                cleaned_descriptions.append(desc)

        # Only add if a job title or company was found
        if job_title or company:
            work_experiences_data.append(
                ResumeWorkExperience(
                    company=company,
                    jobTitle=job_title,
                    date=date,
                    descriptions=cleaned_descriptions,
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
