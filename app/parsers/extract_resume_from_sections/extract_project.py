import re
from typing import List, Tuple, Dict, Optional
from app.parsers.types import (
    FeatureSets,
    ResumeSectionToLinesMap,
    TextScores,
    TextItem,
    Line,
    Lines,
)
from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.parsers.extract_resume_from_sections.lib.subsections import (
    divide_section_into_subsections,
)
from app.parsers.extract_resume_from_sections.lib.common_features import (
    DATE_FEATURE_SETS,
    get_has_text,
    is_bold,
    is_likely_tech_stack,
    match_date_range_pattern,
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
    BULLET_REGEX,
)
from app.models import ResumeProject


# (is_project_title_candidate and PROJECT_TITLE_FS from previous refinement should be good)
def is_project_title_candidate(item: TextItem) -> bool:
    text = item.text.strip()
    if len(text.split()) > 7 or text.count(",") > 1 or text.endswith((".", ":")):
        return False
    if text.lower().startswith("tools:") or text.lower().startswith("technologies:"):
        return False
    if (
        is_likely_tech_stack(item)
        and len(text.split()) > 1
        and (text.count(",") > 0 or text.count("/") > 0)
    ):
        return False
    return True


PROJECT_TITLE_FS: FeatureSets = [
    (is_bold, 3),
    (is_project_title_candidate, 2),
    (
        lambda item: item.text[0].isupper()
        and len(item.text.split()) <= 5
        and len(item.text) > 3,
        1,
    ),
    (is_likely_tech_stack, -5),
    (match_date_range_pattern, -4, False),
    (lambda item: BULLET_REGEX.match(item.text.strip()) is not None, -5),
]


def extract_project(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeProject], List[Dict[str, TextScores]]]:
    projects_data: List[ResumeProject] = []
    projects_scores_debug_list: List[Dict[str, TextScores]] = []

    project_lines_all = get_section_lines_by_keywords(
        sections, ["project", "portfolio", "publication", "personal project"]
    )
    subsections = divide_section_into_subsections(project_lines_all)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue

        num_header_candidate_lines = min(2, len(subsection_lines))
        header_candidate_items = [
            item
            for line in subsection_lines[:num_header_candidate_lines]
            for item in line
        ]
        all_items_in_subsection = [item for line in subsection_lines for item in line]

        project_name, project_name_scores = get_text_with_highest_feature_score(
            header_candidate_items, PROJECT_TITLE_FS, False
        )
        date, date_scores = get_text_with_highest_feature_score(
            all_items_in_subsection, DATE_FEATURE_SETS
        )

        # Refined logic for description start
        descriptions_start_line_idx = 0
        # Try to find where the project title or date line ends
        title_or_date_line_idx = -1
        if project_name:
            for idx, line_obj in enumerate(subsection_lines):
                if any(project_name in item.text for item in line_obj):
                    title_or_date_line_idx = max(title_or_date_line_idx, idx)
                    break
        if date:  # Date can be on same line or different line
            for idx, line_obj in enumerate(subsection_lines):
                if any(date in item.text for item in line_obj):
                    title_or_date_line_idx = max(title_or_date_line_idx, idx)
                    break  # Assuming date appears once prominently per project near title

        descriptions_start_line_idx = (
            title_or_date_line_idx + 1 if title_or_date_line_idx != -1 else 0
        )

        # Check for "Tools:" line after title/date, and shift desc_start if found
        if descriptions_start_line_idx < len(subsection_lines):
            potential_tools_line = subsection_lines[descriptions_start_line_idx]
            tools_line_text = " ".join(
                item.text.lower() for item in potential_tools_line
            ).strip()
            if tools_line_text.startswith("tools:") or tools_line_text.startswith(
                "technologies:"
            ):
                descriptions_start_line_idx += 1

        # Bullet points are a strong indicator if they start later
        bullet_desc_idx = get_descriptions_line_idx(subsection_lines)
        if bullet_desc_idx is not None:
            descriptions_start_line_idx = max(
                descriptions_start_line_idx, bullet_desc_idx
            )

        descriptions_start_line_idx = min(
            descriptions_start_line_idx, len(subsection_lines)
        )

        description_content_lines = subsection_lines[descriptions_start_line_idx:]
        raw_descriptions = (
            get_bullet_points_from_lines(description_content_lines)
            if description_content_lines
            else []
        )

        cleaned_descriptions = []
        for desc_idx, desc in enumerate(raw_descriptions):
            clean_d = desc.strip()
            # More careful cleaning of date/tools only if they are the prefix of the first description
            if desc_idx == 0:
                if date and clean_d.startswith(date):
                    clean_d = clean_d[len(date) :].strip()
                if clean_d.lower().startswith("tools:") or clean_d.lower().startswith(
                    "technologies:"
                ):
                    parts = re.split(r"tools:|technologies:", clean_d, 1, re.IGNORECASE)
                    clean_d = parts[1].strip() if len(parts) > 1 else ""

            # General OCR noise cleaning was moved to read_pdf.py
            if clean_d:
                cleaned_descriptions.append(clean_d)

        # If project_name is an OCR artifact or empty, and we have descriptions, try to find a better title
        if (not project_name or len(project_name) < 3) and cleaned_descriptions:
            # Try to use the first line of the subsection IF it's not a bullet and not tech stack
            first_line_text_items = subsection_lines[0]
            if first_line_text_items:
                first_line_full_text = " ".join(
                    it.text for it in first_line_text_items
                ).strip()
                if (
                    first_line_full_text
                    and not BULLET_REGEX.match(first_line_full_text)
                    and not is_likely_tech_stack(
                        TextItem(
                            text=first_line_full_text,
                            x=0,
                            y=0,
                            width=0,
                            height=0,
                            fontName="",
                        )
                    )
                ):
                    if len(first_line_full_text.split()) < 7:  # Reasonable title length
                        project_name = first_line_full_text

        if project_name or cleaned_descriptions:
            projects_data.append(
                ResumeProject(
                    project=project_name, date=date, descriptions=cleaned_descriptions
                )
            )
            projects_scores_debug_list.append(
                {"project_scores": project_name_scores, "date_scores": date_scores}
            )  # Store original scores

    return projects_data, projects_scores_debug_list
