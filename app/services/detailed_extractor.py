# app/services/detailed_extractor.py
import io
import re
from typing import List, Optional, Tuple

# Ensure TextItem, Line, and Lines are imported from resume_segmenter
from app.services.resume_segmenter import Line, Lines, TextItem
from app.models.extraction_log import WorkExperienceEntry, ProjectEntry, EducationEntry

# --- Regex Patterns ---
month_pattern_str = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?"
year_pattern_str = r"\d{4}"
month_year_pattern_str = rf"\b{month_pattern_str}\s+{year_pattern_str}\b"
date_separator_pattern_str = r"\s*(?:-|–|—|\bto\b)\s*"  # Matches "-", "–", "—", or "to"

full_date_pattern_str = (
    rf"({month_year_pattern_str})"
    rf"(?:{date_separator_pattern_str}"
    rf"({month_year_pattern_str}|\bPresent\b|\bExpected\b))?"
    rf"(?:\s*\(Expected\))?"
)
DATE_PATTERN = re.compile(full_date_pattern_str, re.IGNORECASE)

year_only_pattern_str = (
    rf"(\b{year_pattern_str}\b)"
    rf"(?:{date_separator_pattern_str}"
    rf"(\b{year_pattern_str}\b|\bPresent\b|\bExpected\b))?"
    rf"(?:\s*\(Expected\))?"
)
YEAR_PATTERN = re.compile(year_only_pattern_str, re.IGNORECASE)

GPA_PATTERN = re.compile(
    r"\b(?:GPA|gpa)[:\s]*([\d\.]+(?:\s*/\s*[\d\.]+)?)\b", re.IGNORECASE
)
LOCATION_PATTERN = re.compile(r"\b([A-Za-z\s\.'-]+,\s*[A-Z]{2})\b")

# --- Keyword Lists ---
JOB_TITLE_KEYWORDS = [
    "engineer",
    "developer",
    "manager",
    "analyst",
    "specialist",
    "intern",
    "consultant",
    "architect",
    "lead",
    "president",
    "officer",
    "coordinator",
    "assistant",
    "associate",
    "scientist",
    "researcher",
    "designer",
    "representative",
    "fellow",
    "instructor",
    "head",
]
DESCRIPTION_START_KEYWORDS = [
    "developed",
    "managed",
    "led",
    "responsible for",
    "created",
    "implemented",
    "designed",
    "analyzed",
    "tested",
    "collaborated",
    "assisted",
    "supported",
    "orchestrated",
    "leveraged",
    "utilized",
    "contributed",
    "participated",
    "conducted",
    "achieved",
    "spearheaded",
    "executed",
    "oversaw",
]
BULLET_CHARS = "•◦*-–"
DEGREE_KEYWORDS = [
    "bachelor of science",
    "b.s.",
    "bs",
    "b.sc.",
    "bsc",
    "master of science",
    "m.s.",
    "ms",
    "m.sc.",
    "msc",
    "doctor of philosophy",
    "ph.d.",
    "phd",
    "associate of arts",
    "a.a.",
    "associate of science",
    "a.s.",
    "bachelor of arts",
    "b.a.",
    "ba",
    "master of arts",
    "m.a.",
    "ma",
    "high school diploma",
    "ged",
]
INSTITUTION_KEYWORDS = ["university", "college", "institute", "school", "academy"]
RELEVANT_COURSES_KEYWORDS = [
    "relevant courses",
    "coursework",
    "relevant course work",
    "selected courses",
]
HONORS_KEYWORDS = [
    "honors",
    "dean's list",
    "president's list",
    "scholar",
    "scholarship",
    "cum laude",
    "magna cum laude",
    "summa cum laude",
]


# --- Helper Functions ---
def line_has_job_title_keyword(line_text: str) -> bool:
    return any(keyword in line_text.lower() for keyword in JOB_TITLE_KEYWORDS)


def line_starts_with_description_keyword_or_bullet(line_text: str) -> bool:
    line_lower_stripped = line_text.lower().strip()
    if not line_lower_stripped:
        return False
    if line_lower_stripped[0] in BULLET_CHARS:
        return True
    return any(
        line_lower_stripped.startswith(keyword)
        for keyword in DESCRIPTION_START_KEYWORDS
    )


def extract_dates_from_line(line_text: str) -> Optional[str]:  # DEFINITION
    match = DATE_PATTERN.search(line_text)
    if match:
        return match.group(0).strip()
    year_match = YEAR_PATTERN.search(line_text)
    if year_match:
        return year_match.group(0).strip()
    return None


def is_likely_company_name(line_items: Line, line_text: str) -> bool:
    if not line_items:
        return False
    if extract_dates_from_line(line_text):
        return False
    if line_starts_with_description_keyword_or_bullet(line_text):
        return False
    if re.search(
        r"\b(Inc\.?|Ltd\.?|LLC|Corp\.?|Corporation|Group|Solutions|Technologies|University|College|School|Institute|Foundation|Systems|Labs)\b",
        line_text,
        re.IGNORECASE,
    ):
        return True
    if line_text.istitle() and 1 <= len(line_text.split()) <= 6:
        first_word_lower = line_text.split()[0].lower()
        if first_word_lower not in ["the", "a", "an"] and (
            first_word_lower.endswith("er")
            or first_word_lower.endswith("or")
            or first_word_lower.endswith("ist")
        ):
            if not any(
                kw in line_text.lower()
                for kw in ["university", "college", "school", "institute"]
            ):
                return False
        return True
    return False


# --- Subsection Identification ---
def identify_experience_subsections(section_lines: Lines) -> List[Lines]:
    subsections: List[Lines] = []
    current_subsection: Lines = []
    if not section_lines:
        return []
    for i, line_items in enumerate(section_lines):
        line_text = " ".join(item.text for item in line_items).strip()
        if not line_text:
            continue
        is_potential_header = False
        if line_items:
            first_item_is_bold = line_items[0].is_bold
            if (
                first_item_is_bold
                and not line_starts_with_description_keyword_or_bullet(line_text)
                and len(line_text.split()) < 7
            ):
                is_potential_header = True
            elif extract_dates_from_line(line_text) and len(line_text.split()) < 6:
                if not current_subsection or not extract_dates_from_line(
                    " ".join(item.text for item in current_subsection[-1])
                ):
                    is_potential_header = True
        if is_potential_header and current_subsection:
            if (
                current_subsection[0] and current_subsection[0][0].is_bold
            ):  # Previous line was already a bold header
                subsections.append(current_subsection)
                current_subsection = [line_items]
            else:
                current_subsection.append(line_items)
        else:
            current_subsection.append(line_items)
    if current_subsection:
        subsections.append(current_subsection)
    if not subsections and section_lines:
        return [section_lines]
    return subsections


# --- Detail Extraction Functions ---
def extract_experience_details(
    experience_section_lines: Lines,
) -> List[WorkExperienceEntry]:
    extracted_entries: List[WorkExperienceEntry] = []
    job_subsections = identify_experience_subsections(experience_section_lines)
    for subsection_lines in job_subsections:
        if not subsection_lines:
            continue
        entry = WorkExperienceEntry()
        consumed_line_indices = set()

        for i, line_items in enumerate(subsection_lines):  # Find Dates
            if i in consumed_line_indices:
                continue
            line_text = " ".join(item.text for item in line_items).strip()
            if not line_text:
                continue
            dates = extract_dates_from_line(line_text)  # CALL
            if dates and len(line_text.split()) <= 6:
                entry.dates = dates
                consumed_line_indices.add(i)
                break
        for i, line_items in enumerate(subsection_lines):  # Find Job Title (bold)
            if i in consumed_line_indices:
                continue
            line_text = " ".join(item.text for item in line_items).strip()
            if not line_text:
                continue
            if (
                line_items
                and line_items[0].is_bold
                and line_has_job_title_keyword(line_text)
            ):
                entry.job_title = line_text
                consumed_line_indices.add(i)
                break
        if not entry.job_title:  # Find Job Title (not bold)
            for i, line_items in enumerate(subsection_lines):
                if i in consumed_line_indices:
                    continue
                line_text = " ".join(item.text for item in line_items).strip()
                if not line_text:
                    continue
                if line_has_job_title_keyword(line_text):
                    entry.job_title = line_text
                    consumed_line_indices.add(i)
                    break
        for i, line_items in enumerate(subsection_lines):  # Find Company
            if i in consumed_line_indices:
                continue
            line_text = " ".join(item.text for item in line_items).strip()
            if not line_text:
                continue
            if is_likely_company_name(line_items, line_text):  # CALL
                entry.company_name = line_text
                consumed_line_indices.add(i)
                break
        for i, line_items in enumerate(subsection_lines):  # Find Location
            if i in consumed_line_indices:
                continue
            line_text = " ".join(item.text for item in line_items).strip()
            if not line_text:
                continue
            if (
                "," in line_text
                and len(line_text.split(",")) == 2
                and len(line_text.split()) <= 5
                and not extract_dates_from_line(line_text)
            ):  # CALL
                entry.location = line_text
                consumed_line_indices.add(i)
                break
        for i, line_items in enumerate(subsection_lines):  # Remaining are description
            if i in consumed_line_indices:
                continue
            line_text = " ".join(item.text for item in line_items).strip()
            if line_text:
                entry.description_lines.append(line_text)
        if entry.job_title or entry.company_name or entry.description_lines:
            extracted_entries.append(entry)
    return extracted_entries


def extract_project_details(project_section_lines: Lines) -> List[ProjectEntry]:
    extracted_entries: List[ProjectEntry] = []
    current_project_lines: Lines = []
    for line_idx, line_items in enumerate(project_section_lines):
        line_text = " ".join(item.text for item in line_items).strip()
        if not line_text:
            continue
        is_potential_project_name_line = False
        if line_items and line_items[0].is_bold:
            if (
                not line_text.lower().startswith("tools:")
                and not line_text.lower().startswith("technologies:")
                and len(line_text.split()) < 10
            ):
                is_potential_project_name_line = True
        if is_potential_project_name_line and current_project_lines:
            entry = ProjectEntry()
            if current_project_lines:
                entry.project_name = " ".join(
                    item.text for item in current_project_lines[0]
                ).strip()
                temp_desc_lines, temp_tech_lines = [], []
                for proj_line_item_list in current_project_lines[1:]:
                    proj_line_text_item = " ".join(
                        item.text for item in proj_line_item_list
                    ).strip()
                    if proj_line_text_item.lower().startswith(
                        "tools:"
                    ) or proj_line_text_item.lower().startswith("technologies:"):
                        tech_part = (
                            proj_line_text_item.split(":", 1)[1].strip()
                            if ":" in proj_line_text_item
                            else proj_line_text_item
                        )
                        temp_tech_lines.extend(
                            [t.strip() for t in tech_part.split(",") if t.strip()]
                        )
                    elif not entry.dates and extract_dates_from_line(
                        proj_line_text_item
                    ):  # CALL
                        entry.dates = extract_dates_from_line(proj_line_text_item)
                    else:
                        temp_desc_lines.append(proj_line_text_item)
                entry.description_lines = [ln for ln in temp_desc_lines if ln.strip()]
                entry.technologies_used = list(set(temp_tech_lines))
                if entry.project_name or entry.description_lines:
                    extracted_entries.append(entry)
            current_project_lines = [line_items]
        else:
            current_project_lines.append(line_items)
    if current_project_lines:  # Process last project
        entry = ProjectEntry()
        if current_project_lines:
            entry.project_name = " ".join(
                item.text for item in current_project_lines[0]
            ).strip()
            temp_desc_lines, temp_tech_lines = [], []
            for proj_line_item_list in current_project_lines[1:]:
                proj_line_text_item = " ".join(
                    item.text for item in proj_line_item_list
                ).strip()
                if proj_line_text_item.lower().startswith(
                    "tools:"
                ) or proj_line_text_item.lower().startswith("technologies:"):
                    tech_part = (
                        proj_line_text_item.split(":", 1)[1].strip()
                        if ":" in proj_line_text_item
                        else proj_line_text_item
                    )
                    temp_tech_lines.extend(
                        [t.strip() for t in tech_part.split(",") if t.strip()]
                    )
                elif not entry.dates and extract_dates_from_line(
                    proj_line_text_item
                ):  # CALL
                    entry.dates = extract_dates_from_line(proj_line_text_item)
                else:
                    temp_desc_lines.append(proj_line_text_item)
            entry.description_lines = [ln for ln in temp_desc_lines if ln.strip()]
            entry.technologies_used = list(set(temp_tech_lines))
            if entry.project_name or entry.description_lines:
                extracted_entries.append(entry)
    return extracted_entries


def extract_education_details(education_section_lines: Lines) -> List[EducationEntry]:
    extracted_entries: List[EducationEntry] = []
    if not education_section_lines:
        return []
    entry = EducationEntry()
    remaining_lines_for_details: List[str] = []
    for i, line_items in enumerate(education_section_lines):
        line_text = " ".join(item.text for item in line_items).strip()
        if not line_text:
            continue
        consumed_by_specific_field = False
        if not entry.graduation_date:
            date_match = extract_dates_from_line(line_text)  # CALL
            if date_match:
                entry.graduation_date = date_match
                line_text_without_date = line_text.replace(date_match, "").strip()
                if (
                    not line_text_without_date
                    or line_text_without_date.lower() == "(expected)"
                ):
                    consumed_by_specific_field = True
                else:
                    line_text = line_text_without_date
        if not entry.gpa:
            gpa_match = GPA_PATTERN.search(line_text)
            if gpa_match:
                entry.gpa = gpa_match.group(1).strip()
                line_text_without_gpa = GPA_PATTERN.sub("", line_text).strip()
                if not line_text_without_gpa:
                    consumed_by_specific_field = True
                else:
                    line_text = line_text_without_gpa
        if consumed_by_specific_field:
            continue
        if not entry.institution_name and any(
            kw in line_text.lower() for kw in INSTITUTION_KEYWORDS
        ):
            entry.institution_name = line_text
            location_match = LOCATION_PATTERN.search(line_text)
            if location_match and not entry.location:
                entry.location = location_match.group(1).strip()
                entry.institution_name = (
                    entry.institution_name.replace(entry.location, "")
                    .replace(",", "")
                    .strip()
                )
            consumed_by_specific_field = True
        if not entry.degree_name and any(
            kw in line_text.lower() for kw in DEGREE_KEYWORDS
        ):
            entry.degree_name = line_text
            if "minor in" in line_text.lower():
                parts = re.split(r"minor in", line_text, flags=re.IGNORECASE)
                entry.degree_name = parts[0].strip().rstrip(",")
                entry.minor = parts[1].strip()
            if "major in" in (entry.degree_name or "").lower():
                parts = re.split(r"major in", entry.degree_name, flags=re.IGNORECASE)
                entry.degree_name = parts[0].strip().rstrip(",")
                entry.major = parts[1].strip()
            elif " in " in (entry.degree_name or "") and not entry.major:
                parts = re.split(r"\s+in\s+", entry.degree_name, 1, flags=re.IGNORECASE)
                if len(parts) > 1:
                    entry.degree_name = parts[0].strip()
                    entry.major = parts[1].strip()
            consumed_by_specific_field = True
        if not entry.location and not consumed_by_specific_field:
            location_match = LOCATION_PATTERN.search(line_text)
            if location_match:
                entry.location = location_match.group(1).strip()
                consumed_by_specific_field = True
        if any(kw in line_text.lower() for kw in RELEVANT_COURSES_KEYWORDS):
            courses_text = line_text
            for kw in RELEVANT_COURSES_KEYWORDS:
                courses_text = re.sub(
                    rf"{re.escape(kw)}:?\s*", "", courses_text, flags=re.IGNORECASE
                ).strip()
            if courses_text:
                entry.relevant_courses = [
                    c.strip() for c in courses_text.split(",") if c.strip()
                ]
            consumed_by_specific_field = True
        if (
            any(kw in line_text.lower() for kw in HONORS_KEYWORDS)
            and not consumed_by_specific_field
        ):
            if not (entry.degree_name and line_text in entry.degree_name):
                entry.honors_awards.append(line_text)
        if not consumed_by_specific_field and line_text:
            remaining_lines_for_details.append(line_text)
    if not entry.institution_name and remaining_lines_for_details:
        if any(
            kw in remaining_lines_for_details[0].lower() for kw in INSTITUTION_KEYWORDS
        ):
            entry.institution_name = remaining_lines_for_details.pop(0)
    if not entry.degree_name and remaining_lines_for_details:
        if any(kw in remaining_lines_for_details[0].lower() for kw in DEGREE_KEYWORDS):
            entry.degree_name = remaining_lines_for_details.pop(0)
            if "minor in" in (entry.degree_name or "").lower():
                parts = re.split(r"minor in", entry.degree_name, flags=re.IGNORECASE)
                entry.degree_name = parts[0].strip().rstrip(",")
                entry.minor = parts[1].strip()
            if "major in" in (entry.degree_name or "").lower() and not entry.major:
                parts = re.split(r"major in", entry.degree_name, 1, flags=re.IGNORECASE)
                entry.degree_name = parts[0].strip().rstrip(",")
                entry.major = parts[1].strip()
    if (
        entry.institution_name
        or entry.degree_name
        or entry.gpa
        or entry.graduation_date
    ):
        extracted_entries.append(entry)
    return extracted_entries
