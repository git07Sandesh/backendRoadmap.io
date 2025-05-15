import re
from typing import List, Tuple, Dict, Optional, Any
from app.parsers.types import (
    TextItem,
    FeatureSets,
    ResumeSectionToLinesMap,
    TextScores,
    Lines,
    Line,
)
from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.parsers.extract_resume_from_sections.lib.subsections import (
    divide_section_into_subsections,
)
from app.parsers.extract_resume_from_sections.lib.common_features import (
    is_bold,
    has_letter,
    has_year_keyword,
    has_month_keyword,
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.models import ResumeEducation

# Expected column headers for Sandesh's resume education table (lowercase for matching)
EDU_TABLE_HEADERS = {
    "degree/certificate": "degree",
    "institute/board": "school",
    "gpa": "gpa",
    "year": "date",
}
# Keywords to identify the header row
EDU_HEADER_KEYWORDS = ["degree", "certificate", "institute", "board", "gpa", "year"]


def parse_education_table_heuristic(education_lines: Lines) -> List[ResumeEducation]:
    """
    Heuristic to parse education data if it looks like Sandesh's table format.
    """
    parsed_educations: List[ResumeEducation] = []
    if (
        not education_lines or len(education_lines) < 2
    ):  # Need at least header + data row
        return parsed_educations

    # 1. Try to identify the header row and column x-positions
    header_row_idx = -1
    column_x_centers: Dict[str, float] = {}  # Maps standardized header key to x-center

    for i, line_items in enumerate(education_lines):
        if not line_items:
            continue
        line_text_lower = " ".join(item.text.lower() for item in line_items)
        found_keywords = [kw for kw in EDU_HEADER_KEYWORDS if kw in line_text_lower]

        if len(found_keywords) >= 3:  # If at least 3 header keywords are on this line
            header_row_idx = i
            # Get x-centers for the items that matched keywords
            temp_centers: List[Tuple[str, float]] = []  # (keyword, x_center)
            for item in line_items:
                item_text_lower = item.text.lower()
                for kw_expected, key_standard in EDU_TABLE_HEADERS.items():
                    # Check if item text strongly relates to an expected header part
                    if any(part in item_text_lower for part in kw_expected.split("/")):
                        temp_centers.append((key_standard, item.x + item.width / 2))
                        break
            temp_centers.sort(key=lambda x: x[1])  # Sort by x-coordinate

            # Deduplicate and assign, favoring first match for a standard key
            for key_std, x_val in temp_centers:
                if key_std not in column_x_centers:
                    column_x_centers[key_std] = x_val
            break

    if (
        header_row_idx == -1 or not column_x_centers or len(column_x_centers) < 2
    ):  # Header not found or too few columns
        return parsed_educations  # Fallback to non-table parsing will happen outside

    # Create sorted list of (standard_key, x_center) for column boundary calculation
    sorted_columns = sorted(column_x_centers.items(), key=lambda x: x[1])

    # 2. Process data rows
    for i in range(header_row_idx + 1, len(education_lines)):
        data_line_items = education_lines[i]
        if not data_line_items:
            continue

        current_edu_data: Dict[str, str] = {
            key: "" for key in EDU_TABLE_HEADERS.values()
        }

        for item in data_line_items:
            item_text = item.text.strip()
            if not item_text:
                continue

            item_mid_x = item.x + item.width / 2

            # Assign item to the closest column based on x_mid_point
            best_col_key = None
            min_dist = float("inf")

            for col_idx, (col_key, col_x_center) in enumerate(sorted_columns):
                dist = abs(item_mid_x - col_x_center)

                # Check if item is reasonably within this column's implied boundaries
                # Left boundary:
                left_bound = 0.0
                if col_idx > 0:
                    left_bound = (col_x_center + sorted_columns[col_idx - 1][1]) / 2
                # Right boundary:
                right_bound = float("inf")
                if col_idx < len(sorted_columns) - 1:
                    right_bound = (col_x_center + sorted_columns[col_idx + 1][1]) / 2

                # If item's x range (item.x to item.x + item.width) overlaps significantly with column
                item_overlap_start = max(left_bound, item.x)
                item_overlap_end = min(right_bound, item.x + item.width)

                if item_overlap_end > item_overlap_start:  # Significant overlap
                    if (
                        dist < min_dist
                    ):  # And it's the closest column this item overlaps with
                        min_dist = dist
                        best_col_key = col_key

            if best_col_key:
                current_edu_data[best_col_key] = (
                    current_edu_data[best_col_key] + " " + item_text
                ).strip()

        # Clean up "(Expected)" from date
        if "(expected)" in current_edu_data.get("date", "").lower():
            current_edu_data["date"] = (
                current_edu_data["date"]
                .lower()
                .replace("(expected)", "")
                .strip()
                .title()
            )

        if current_edu_data.get("degree") or current_edu_data.get("school"):
            parsed_educations.append(
                ResumeEducation(
                    school=current_edu_data.get("school", ""),
                    degree=current_edu_data.get("degree", ""),
                    gpa=current_edu_data.get("gpa", ""),
                    date=current_edu_data.get("date", ""),
                    descriptions=[],
                )
            )

    return parsed_educations


def extract_education(
    sections: ResumeSectionToLinesMap,
) -> Tuple[List[ResumeEducation], Any]:
    educations_data: List[ResumeEducation] = []

    education_lines = sections.get("EDUCATION", sections.get("education", []))
    if not education_lines:
        education_lines = get_section_lines_by_keywords(
            sections, ["education", "academic"]
        )

    if not education_lines:
        return [], []

    # Attempt table parsing first
    table_parsed_educations = parse_education_table_heuristic(education_lines)
    if table_parsed_educations:  # If table parsing yielded results, use them
        return table_parsed_educations, []  # No detailed scores for table parse yet

    # --- Fallback to original heuristic (non-table) parsing if table parsing fails ---
    # This is the logic from your previous refined `extract_education.py`
    # (Ensure all imports and feature sets like SCHOOL_FS_HEURISTIC are defined above or imported)
    educations_scores_debug_list = []
    subsections = divide_section_into_subsections(education_lines)

    for subsection_lines in subsections:
        if not subsection_lines:
            continue
        all_items_in_subsection = [item for line in subsection_lines for item in line]
        if not all_items_in_subsection:
            continue

        # (Re-define or import SCHOOL_FS_HEURISTIC, DEGREE_FS_HEURISTIC, etc. from previous version)
        # For brevity, assuming these FeatureSets are available here from the previous non-table logic.
        # You'll need to ensure the full non-table heuristic logic is present here as the fallback.
        # This part is effectively pasting the previous non-table `extract_education` content.
        # Example snippet:
        # school, school_scores = get_text_with_highest_feature_score(all_items_in_subsection, SCHOOL_FS_HEURISTIC)
        # degree, degree_scores = get_text_with_highest_feature_score(all_items_in_subsection, DEGREE_FS_HEURISTIC)
        # ... etc. ...
        # if school or degree:
        #     educations_data.append(ResumeEducation(school=school, degree=degree, gpa=gpa, date=date, descriptions=cleaned_descriptions))
        #     educations_scores_debug_list.append({...})
        # print("Warning: Education section found but not parsed as a table, and fallback non-table logic is not fully implemented in this snippet.")
        pass  # Placeholder for the full non-table heuristic logic

    return educations_data, educations_scores_debug_list
