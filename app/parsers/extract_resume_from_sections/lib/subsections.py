from typing import List, Callable
from app.parsers.types import Lines, Line, Subsections, TextItem
from app.parsers.extract_resume_from_sections.lib.bullet_points import BULLET_POINTS
from app.parsers.extract_resume_from_sections.lib.common_features import is_bold
import math


IsLineNewSubsection = Callable[[Line, Line], bool]


def create_is_line_new_subsection_by_line_gap(lines: Lines) -> IsLineNewSubsection:
    line_gap_to_count: dict[int, int] = {}
    lines_y = [
        line[0].y for line in lines if line and line[0]
    ]  # Ensure line and line[0] exist

    line_gap_with_most_count = 0  # Default for single line or no lines
    max_count = 0

    if len(lines_y) > 1:
        for i in range(1, len(lines_y)):
            # PyMuPDF y increases downwards, so prev_y - curr_y would be negative if curr is below prev.
            # We need absolute difference or ensure order.
            # The original `prevLine[0].y - line[0].y` expects y to increase upwards.
            # For PyMuPDF, if line[i] is visually below lines[i-1], then line[i].y > lines[i-1].y.
            # So, line_gap = lines_y[i] - lines_y[i-1] (current_y - previous_y)
            line_gap = abs(
                math.ceil(lines_y[i]) - math.ceil(lines_y[i - 1])
            )  # Use abs for safety, round for grouping
            if line_gap <= 0:  # Ignore zero or negative gaps (overlaps or same line)
                continue
            line_gap_to_count[line_gap] = line_gap_to_count.get(line_gap, 0) + 1
            if line_gap_to_count[line_gap] > max_count:
                line_gap_with_most_count = line_gap
                max_count = line_gap_to_count[line_gap]

    if (
        line_gap_with_most_count == 0 and lines
    ):  # Fallback if no dominant gap (e.g. all lines equally spaced)
        # Use average height of a text item as a proxy for typical line gap
        avg_item_height = (
            sum(item.height for line in lines for item in line if line)
            / sum(len(line) for line in lines if line)
            if any(lines)
            else 10
        )
        line_gap_with_most_count = round(avg_item_height)

    subsection_line_gap_threshold = line_gap_with_most_count * 1.4
    if subsection_line_gap_threshold == 0:
        subsection_line_gap_threshold = 10  # Min threshold

    def is_line_new_subsection(line: Line, prev_line: Line) -> bool:
        if not line or not prev_line or not line[0] or not prev_line[0]:
            return False
        # current_y - previous_y for PyMuPDF
        gap = round(line[0].y - prev_line[0].y)
        return gap > subsection_line_gap_threshold

    return is_line_new_subsection


def create_subsections(
    lines: Lines, is_line_new_subsection_func: IsLineNewSubsection
) -> Subsections:
    subsections: Subsections = []
    current_subsection: Lines = []
    if not lines:
        return []

    for i, line in enumerate(lines):
        if not line:
            continue  # Skip fully empty lines from earlier processing

        if i == 0:
            current_subsection.append(line)
            continue

        # Need to ensure lines[i-1] was not an empty line if they can exist
        prev_line_idx = i - 1
        # Find the last non-empty previous line
        while prev_line_idx >= 0 and not lines[prev_line_idx]:
            prev_line_idx -= 1

        if prev_line_idx < 0 or is_line_new_subsection_func(line, lines[prev_line_idx]):
            if current_subsection:  # Avoid adding empty subsections
                subsections.append(list(current_subsection))  # Make a copy
            current_subsection = []

        current_subsection.append(line)

    if current_subsection:  # Add the last subsection
        subsections.append(list(current_subsection))

    return subsections


def divide_section_into_subsections(lines: Lines) -> Subsections:
    if not lines:
        return []

    is_line_new_subsection_by_gap = create_is_line_new_subsection_by_line_gap(lines)
    subsections = create_subsections(lines, is_line_new_subsection_by_gap)

    if (
        len(subsections) == 1 and len(lines) > 1
    ):  # If only one subsection but multiple lines, try bold heuristic

        def is_line_new_subsection_by_bold(line: Line, prev_line: Line) -> bool:
            if not line or not prev_line or not line[0] or not prev_line[0]:
                return False

            # Ensure text is not just a bullet point
            line_text_is_bullet = any(
                bullet in line[0].text for bullet in BULLET_POINTS
            )

            if (
                not is_bold(prev_line[0])
                and is_bold(line[0])
                and not line_text_is_bullet
            ):
                return True
            return False

        # Re-evaluate with bold heuristic ONLY if gap heuristic produced a single subsection from multiple lines
        bold_subsections = create_subsections(lines, is_line_new_subsection_by_bold)
        if (
            len(bold_subsections) > 1
        ):  # Only use bold if it actually splits into more subsections
            return bold_subsections

    return subsections
