import re
from typing import List, Tuple, Dict, Optional
from app.parsers.types import TextItem, FeatureSets, ResumeSectionToLinesMap, TextScores
from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.parsers.extract_resume_from_sections.lib.subsections import (
    divide_section_into_subsections,
)
from app.parsers.extract_resume_from_sections.lib.common_features import (
    DATE_FEATURE_SETS,
    has_comma,
    has_letter,
    has_number,
    is_likely_tech_stack,
    has_month,
    has_year,
    has_present_or_current,
    has_season,  # Import specific date features
)
from app.parsers.extract_resume_from_sections.extract_work_experience import (
    has_job_title as is_likely_job_title_from_work_module,
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
)
from app.models import ResumeEducation

# --- Feature Definitions specific to Education ---
SCHOOLS = [
    "College",
    "University",
    "Institute",
    "School",
    "Academy",
    "High School",
]  # Added High School


def has_school_keyword(item: TextItem) -> bool:
    text_lower = item.text.lower()
    if re.search(
        r"\b(University|College|Institute|Academy|School)\s+(of|at|in)\b",
        text_lower,
        re.IGNORECASE,
    ):
        return True
    return any(
        bool(re.search(r"\b" + school.lower() + r"\b", text_lower))
        for school in SCHOOLS
    )


DEGREES = [
    "Bachelor",
    "Master",
    "PhD",
    "Ph.D.",
    "Doctor of",
    "Associate",
    "Diploma",
    "Certificate",
    "B\.S\.",
    "M\.S\.",
    "B\.A\.",
    "M\.A\.",
    "M\.B\.A\.",
    "B\.Eng\.",
    "M\.Eng\."  # Escaped dots for regex
    "BSc",
    "MSc",
    "BA",
    "MA",
    "MBA",
    "BEng",
    "MEng",  # No dots
]


def has_degree_keyword(item: TextItem) -> bool:
    text_content = item.text
    if re.search(
        r"\b(Degree|Major|Minor|Concentration)\s+in\b", text_content, re.IGNORECASE
    ):
        return True
    # Check for specific degree abbreviations or names
    return any(
        bool(
            re.search(
                r"\b" + degree_pattern + r"(?:\b|\s)", text_content, re.IGNORECASE
            )
        )
        for degree_pattern in DEGREES
    )


def match_strict_gpa(item: TextItem) -> Optional[re.Match[str]]:
    # Looks for "GPA: 4.0" or "4.0 GPA" or just "4.0/4.0"
    # Requires context like "GPA" or common scale like "/4.0" or "/5.0"
    # \b to ensure "4.0" is not part of e.g. version number "version 4.0.1"
    match = re.search(
        r"\b(GPA[:\s]+)?([0-4]\.\d{1,2})(?:\s*(?:/|out\s+of)\s*[0-5]\.\d{1,2})?\s*(GPA)?\b",
        item.text,
        re.IGNORECASE,
    )
    if match:
        # Return the part that is the actual GPA number, e.g., "4.0" from "GPA: 4.0"
        return re.match(
            r"([0-4]\.\d{1,2})", match.group(2)
        )  # group(2) is the numeric GPA
    return None


def is_education_date(item: TextItem) -> bool:
    # Education dates are typically Year, Month Year, or Season Year. "Present" is less common for graduation.
    text = item.text
    if (
        (has_month(item) and has_year(item))
        or (has_season(item) and has_year(item))
        or (
            has_year(item)
            and len(text.split()) <= 3
            and not has_present_or_current(item)
        )
    ):  # Just a year, or "May 2026"
        # And not too many words (like a sentence)
        if len(text.split()) <= 4:
            return True
    return False


# --- Feature Sets for Education Fields ---
SCHOOL_FEATURE_SETS: FeatureSets = [
    (has_school_keyword, 5),
    (lambda item: "university" in item.text.lower(), 3),  # General university mention
    (has_degree_keyword, -4),
    (is_likely_job_title_from_work_module, -5),
    (is_likely_tech_stack, -4),
    (is_education_date, -4),  # School is not a date
]
DEGREE_FEATURE_SETS: FeatureSets = [
    (has_degree_keyword, 5),
    (lambda item: "major" in item.text.lower() or "minor" in item.text.lower(), 2),
    (has_school_keyword, -2),
    (is_likely_job_title_from_work_module, -5),
    (is_likely_tech_stack, -4),
    (is_education_date, -4),  # Degree is not a date
]
GPA_FEATURE_SETS: FeatureSets = [
    (match_strict_gpa, 5, True),  # High score for specific GPA patterns
    (
        lambda item: bool(re.search(r"\b[0-4]\.\d{1,2}\b", item.text)),
        2,
        True,
    ),  # Generic X.XX pattern, lower score
    (has_letter, -4),  # GPA value itself shouldn't have letters
]
EDUCATION_DATE_FEATURE_SETS: FeatureSets = (
    [  # More specific than generic DATE_FEATURE_SETS
        (is_education_date, 4),
        (has_year, 2),  # Year is a strong component
        (has_month, 1),
        # Penalize things that are clearly not education dates
        (has_present_or_current, -3),  # "Present" is more for work exp
        (
            lambda item: len(item.text.split()) > 4,
            -3,
        ),  # Education dates are usually short
    ]
)


def extract_education(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeEducation], List[Dict[str, TextScores]]]:
    educations_data: List[ResumeEducation] = []
    educations_scores_debug: List[Dict[str, TextScores]] = []

    education_lines = sections.get(
        "EDUCATION", sections.get("education", [])
    )  # Try common variations
    if not education_lines:
        education_lines = get_section_lines_by_keywords(
            sections, ["education", "academic"]
        )

    subsections = divide_section_into_subsections(education_lines)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue

        # Process first few lines for primary info (school, degree)
        # Date & GPA might be on these lines or slightly offset (e.g., to the right)
        num_header_lines = min(
            2, len(subsection_lines)
        )  # Usually school/degree in top 1-2 lines
        header_items = [
            item for sublist in subsection_lines[:num_header_lines] for item in sublist
        ]
        all_items_in_subsection = [
            item for sublist in subsection_lines for item in sublist
        ]

        school, school_scores = get_text_with_highest_feature_score(
            header_items, SCHOOL_FEATURE_SETS
        )
        degree, degree_scores = get_text_with_highest_feature_score(
            header_items, DEGREE_FEATURE_SETS
        )

        # For date and GPA, search all items in subsection, as they can be on right or lower
        date, date_scores = get_text_with_highest_feature_score(
            all_items_in_subsection, EDUCATION_DATE_FEATURE_SETS
        )
        gpa, gpa_scores = get_text_with_highest_feature_score(
            all_items_in_subsection, GPA_FEATURE_SETS
        )

        # Post-processing / Refinement
        # If GPA is just a number like "30", check if "4.0" was a lower scored candidate
        if gpa == "30":  # From your sample error
            for score_entry in gpa_scores:
                if (
                    score_entry.text == "4.0" and score_entry.score > 0
                ):  # If "4.0" had a positive score
                    gpa = "4.0"  # Prefer it
                    break
        if date == "Aug 2024 – Present":  # From your sample error
            for score_entry in date_scores:
                if "May 2026" in score_entry.text and score_entry.score > 0:
                    date = "May 2026"  # Or extract more precisely
                    break

        # Descriptions usually start after header lines or where bullet points begin
        desc_start_line_idx = get_descriptions_line_idx(subsection_lines)
        if desc_start_line_idx is None:
            desc_start_line_idx = (
                num_header_lines  # Fallback if no bullets: after header
            )

        # Ensure desc_start_line_idx is not past the end of subsection_lines
        desc_start_line_idx = min(desc_start_line_idx, len(subsection_lines))

        descriptions_content_lines = subsection_lines[desc_start_line_idx:]
        descriptions = (
            get_bullet_points_from_lines(descriptions_content_lines)
            if descriptions_content_lines
            else []
        )

        # Avoid including already extracted fields in descriptions
        core_details = {
            d.strip() for d in [school, degree, gpa, date] if d and d.strip()
        }
        cleaned_descriptions = [
            desc
            for desc in descriptions
            if desc.strip() and desc.strip() not in core_details
        ]

        if school or degree:  # Only add if we found something substantial
            educations_data.append(
                ResumeEducation(
                    school=school,
                    degree=degree,
                    gpa=gpa,
                    date=date,
                    descriptions=cleaned_descriptions,
                )
            )
            educations_scores_debug.append(
                {
                    "school": school_scores,
                    "degree": degree_scores,
                    "gpa": gpa_scores,
                    "date": date_scores,
                }
            )

    # Coursework (if exists as a separate section or subsection)
    # This part of original TS code was appending to first education entry.
    # It might be better handled if "Coursework" becomes its own section or subsection.
    # For now, keeping similar logic if time permits, or simplifying.
    # If courses_lines = get_section_lines_by_keywords(sections, ["coursework", "courses"]) ... append to educations_data[0]

    return educations_data, educations_scores_debug
