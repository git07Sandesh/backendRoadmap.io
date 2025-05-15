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
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
)
from app.models import ResumeEducation  # For return type


SCHOOLS = ["College", "University", "Institute", "School", "Academy", "BASIS", "Magnet"]


def has_school(item: TextItem) -> bool:
    return any(school.lower() in item.text.lower() for school in SCHOOLS)


DEGREES = [
    "Associate",
    "Bachelor",
    "Master",
    "PhD",
    "Ph.D.",
    "M.S.",
    "B.S.",
    "B.A.",
    "M.A.",
]  # Added more common ones


def has_degree(item: TextItem) -> bool:
    # Check for full words first for higher precision
    for degree in DEGREES:
        # Escape the degree for regex, especially the dot.
        escaped_degree = degree.replace(".", r"\.")
        # Construct the pattern.
        # The \b ensures word boundaries. [ .,s]? allows for optional space, comma, dot, or 's' after degree
        pattern = (
            rf"\b{escaped_degree}[ .,s]?"  # Use raw f-string for the whole pattern
        )
        if re.search(
            pattern, item.text, re.IGNORECASE
        ):  # Added IGNORECASE for robustness
            return True

    # Fallback to original regex for abbreviations like AA, B.S., MBA
    if re.search(
        r"\b([ABM][A-Z\.]+)\b", item.text, re.IGNORECASE
    ):  # \b for word boundaries, added IGNORECASE
        return True
    return False  # Default


def match_gpa(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"[0-4]\.\d{1,2}", item.text)


def match_grade(item: TextItem) -> Optional[re.Match[str]]:
    match = re.search(
        r"(\d{1,3}(?:\.\d{1,2})?)", item.text
    )  # Match numbers like 95, 3.5, 98.5
    if match:
        try:
            grade = float(match.group(1))
            if (
                0 <= grade <= 110
            ):  # Assuming max grade/percentage is 110 (e.g. for some Indian systems with >100%)
                return match
        except ValueError:
            pass
    return None


SCHOOL_FEATURE_SETS: FeatureSets = [
    (has_school, 4),
    (has_degree, -4),
    (has_number, -4),
]
DEGREE_FEATURE_SETS: FeatureSets = [
    (has_degree, 4),
    (has_school, -4),
    (has_number, -3),
]
GPA_FEATURE_SETS: FeatureSets = [
    (match_gpa, 4, True),
    (match_grade, 3, True),
    (has_comma, -3),
    (has_letter, -4),
]


def extract_education(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeEducation], List[Dict[str, TextScores]]]:
    educations_data: List[ResumeEducation] = []
    educations_scores_debug: List[Dict[str, TextScores]] = []

    education_lines = get_section_lines_by_keywords(
        sections, ["education", "academic"]
    )  # Added "academic"
    subsections = divide_section_into_subsections(education_lines)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue
        text_items = [item for sublist in subsection_lines for item in sublist]

        school, school_scores = get_text_with_highest_feature_score(
            text_items, SCHOOL_FEATURE_SETS
        )
        degree, degree_scores = get_text_with_highest_feature_score(
            text_items, DEGREE_FEATURE_SETS
        )
        gpa, gpa_scores = get_text_with_highest_feature_score(
            text_items, GPA_FEATURE_SETS
        )
        date, date_scores = get_text_with_highest_feature_score(
            text_items, DATE_FEATURE_SETS
        )

        descriptions: List[str] = []
        descriptions_line_idx = get_descriptions_line_idx(subsection_lines)
        if descriptions_line_idx is not None:  # Check for None
            desc_lines_to_process = subsection_lines[descriptions_line_idx:]
            if desc_lines_to_process:  # Ensure there are lines to process
                descriptions = get_bullet_points_from_lines(desc_lines_to_process)

        educations_data.append(
            ResumeEducation(
                school=school,
                degree=degree,
                gpa=gpa,
                date=date,
                descriptions=descriptions,
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

    if educations_data:  # If any education entry was added
        courses_lines = get_section_lines_by_keywords(
            sections, ["course", "coursework"]
        )
        if courses_lines:
            courses_text = (
                "Courses: "
                + " ".join(item.text for line in courses_lines for item in line).strip()
            )
            if educations_data[0].descriptions:  # Check if descriptions list exists
                educations_data[0].descriptions.append(courses_text)
            else:
                educations_data[0].descriptions = [courses_text]

    return educations_data, educations_scores_debug
