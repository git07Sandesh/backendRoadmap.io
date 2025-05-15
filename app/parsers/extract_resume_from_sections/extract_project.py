from typing import List, Tuple, Dict
from app.parsers.types import FeatureSets, ResumeSectionToLinesMap, TextScores, TextItem
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
    is_likely_tech_stack,  # Import new feature
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    get_bullet_points_from_lines,
    get_descriptions_line_idx,
)
from app.models import ResumeProject


# Features for Project Titles
def is_project_title_candidate(item: TextItem) -> bool:
    # Project titles are often noun phrases, not full sentences, not just tech.
    text = item.text
    if len(text.split()) > 7:
        return False  # Probably too long for a title
    if text.count(",") > 2:
        return False  # Too many commas, likely a list
    if text.endswith(".") or text.endswith(":"):
        return False  # Ends like a sentence or header for list
    return True


PROJECT_TITLE_FEATURE_SET: FeatureSets = [
    (is_bold, 3),
    (is_project_title_candidate, 2),
    (is_likely_tech_stack, -5),  # Strong penalty for tech stacks
    (DATE_FEATURE_SETS[0][0], -4),  # Penalize if it looks like a year (date)
    (
        lambda item: len(item.text.split()) == 1 and not item.text[0].isupper(),
        -3,
    ),  # Single, non-capitalized word unlikely title
]


def extract_project(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeProject], List[Dict[str, TextScores]]]:
    projects_data: List[ResumeProject] = []
    projects_scores_debug: List[Dict[str, TextScores]] = []

    project_lines_all = get_section_lines_by_keywords(
        sections, ["project", "portfolio", "publication", "personal project"]
    )
    subsections = divide_section_into_subsections(project_lines_all)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue

        # Try to find project title in the first 1-2 lines of the subsection.
        # Descriptions usually start with bullet points or after the title and optional tech stack line.

        num_title_candidate_lines = min(
            2, len(subsection_lines)
        )  # Look in first 1 or 2 lines for title
        title_candidate_items = [
            item
            for sublist in subsection_lines[:num_title_candidate_lines]
            for item in sublist
        ]
        all_subsection_items = [
            item for sublist in subsection_lines for item in sublist
        ]

        # Tentatively extract date from the whole subsection first
        date_candidate, date_scores_candidate = get_text_with_highest_feature_score(
            all_subsection_items, DATE_FEATURE_SETS
        )

        # Update project feature set to penalize matching the extracted date
        current_project_feature_set = list(
            PROJECT_TITLE_FEATURE_SET
        )  # Make a mutable copy
        if date_candidate:
            current_project_feature_set.append((get_has_text(date_candidate), -4))

        project_name, project_name_scores = get_text_with_highest_feature_score(
            title_candidate_items,  # Search for title in the top lines
            current_project_feature_set,
            return_empty_string_if_highest_score_is_not_positive=False,  # Allow low score if only candidate
        )

        # Final date extraction (could be same as candidate or refined)
        date, date_scores = get_text_with_highest_feature_score(
            all_subsection_items, DATE_FEATURE_SETS
        )

        # Determine where descriptions start
        # It could be after the project title, or after a tech stack line if present below title.
        descriptions_start_line_idx = 0
        if project_name:  # If a project name was found
            # Find the line containing the project name
            for idx, line_items in enumerate(subsection_lines):
                if any(project_name in item.text for item in line_items):
                    descriptions_start_line_idx = (
                        idx + 1
                    )  # Descriptions start on the next line
                    break

        # If bullet points start earlier, they take precedence for description start
        bullet_desc_idx = get_descriptions_line_idx(subsection_lines)
        if bullet_desc_idx is not None:
            descriptions_start_line_idx = max(
                descriptions_start_line_idx, bullet_desc_idx
            )  # Use bullet index if it's later
            if (
                project_name and bullet_desc_idx <= descriptions_start_line_idx - 1
            ):  # if project name line is before or at bullets
                pass  #  descriptions_start_line_idx is already good
            else:
                descriptions_start_line_idx = bullet_desc_idx

        # Fallback if project_name was empty or not found properly
        if not project_name and bullet_desc_idx is not None:
            descriptions_start_line_idx = bullet_desc_idx
        elif (
            not project_name
        ):  # If no project name and no bullets, assume descriptions start after 1st line
            descriptions_start_line_idx = 1

        descriptions: List[str] = []
        if descriptions_start_line_idx < len(subsection_lines):
            desc_lines_to_process = subsection_lines[descriptions_start_line_idx:]
            if desc_lines_to_process:
                descriptions = get_bullet_points_from_lines(desc_lines_to_process)

        # Clean descriptions: remove project name and tech stack if they got mixed in
        # This part is tricky; the tech stack often appears right after title, before bullets.
        # For now, just ensure project_name itself is not a description.
        cleaned_descriptions = [
            d
            for d in descriptions
            if project_name.lower() not in d.lower() or not project_name
        ]

        if (
            project_name or cleaned_descriptions
        ):  # Add project if there's a title or some descriptions
            projects_data.append(
                ResumeProject(
                    project=project_name, date=date, descriptions=cleaned_descriptions
                )
            )
            projects_scores_debug.append(
                {"project": project_name_scores, "date": date_scores}
            )

    return projects_data, projects_scores_debug
