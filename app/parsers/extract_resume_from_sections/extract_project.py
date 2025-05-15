from typing import List, Tuple, Dict
from app.parsers.types import FeatureSets, ResumeSectionToLinesMap, TextScores
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
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
)
from app.models import ResumeProject  # For return type


def extract_project(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeProject], List[Dict[str, TextScores]]]:
    projects_data: List[ResumeProject] = []
    projects_scores_debug: List[Dict[str, TextScores]] = []

    project_lines = get_section_lines_by_keywords(
        sections, ["project", "portfolio", "publication"]
    )  # Added portfolio, publication
    subsections = divide_section_into_subsections(project_lines)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue

        raw_desc_line_idx = get_descriptions_line_idx(subsection_lines)
        # Default to 1 if no bullet points found, as per original TS logic (?? 1)
        descriptions_line_idx = (
            raw_desc_line_idx
            if raw_desc_line_idx is not None
            else (1 if len(subsection_lines) > 1 else len(subsection_lines))
        )

        slice_end_idx = min(descriptions_line_idx, len(subsection_lines))
        subsection_info_text_items = [
            item for sublist in subsection_lines[:slice_end_idx] for item in sublist
        ]

        date, date_scores = get_text_with_highest_feature_score(
            subsection_info_text_items, DATE_FEATURE_SETS
        )

        project_feature_set: FeatureSets = [
            (is_bold, 2),
            (get_has_text(date), -4),  # Text from 'date' variable
        ]
        project_name, project_name_scores = get_text_with_highest_feature_score(
            subsection_info_text_items,
            project_feature_set,
            False,  # Allow negative highest score
        )

        descriptions: List[str] = []
        if descriptions_line_idx < len(subsection_lines):
            desc_lines_to_process = subsection_lines[descriptions_line_idx:]
            if desc_lines_to_process:
                descriptions = get_bullet_points_from_lines(desc_lines_to_process)

        projects_data.append(
            ResumeProject(project=project_name, date=date, descriptions=descriptions)
        )
        projects_scores_debug.append(
            {"project": project_name_scores, "date": date_scores}
        )

    return projects_data, projects_scores_debug
