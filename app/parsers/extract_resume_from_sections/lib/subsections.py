import re
from typing import List, Callable, Optional
from app.parsers.types import (
    Lines,
    Line,
    Subsections,
    TextItem,
)  # Ensure TextItem is imported
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    BULLET_POINTS_CHARS,
    BULLET_REGEX,
)  # Use refined bullet constants/regex
from app.parsers.extract_resume_from_sections.lib.common_features import (
    is_bold,
    has_letter,
)  # For header checks
import math

# Type alias for the decision function
IsLineNewSubsectionFunc = Callable[[Line, Optional[Line], Lines], bool]


def create_is_line_new_subsection_by_line_gap(
    section_all_lines: Lines,
) -> IsLineNewSubsectionFunc:
    lines_y_coords = [line[0].y for line in section_all_lines if line and line[0]]
    if len(lines_y_coords) <= 1:  # Not enough lines to determine a gap
        return lambda curr, prev, ctx: False  # Always false if no context for gaps

    line_gaps: List[float] = []
    for i in range(1, len(lines_y_coords)):
        gap = abs(lines_y_coords[i] - lines_y_coords[i - 1])
        if gap > 2.0:  # Ignore very small gaps (likely within same text block)
            line_gaps.append(gap)

    if not line_gaps:  # No significant gaps found
        # Fallback: estimate typical line height from text items if no gaps.
        # This means lines are likely tightly packed.
        all_items = [
            item for line_obj in section_all_lines for item in line_obj if line_obj
        ]
        if not all_items:
            typical_line_gap = 12.0  # Default
        else:
            typical_line_gap = sum(item.height for item in all_items) / len(all_items)
    else:
        # Use median or mode of gaps for robustness against outliers
        line_gaps.sort()
        if line_gaps:
            typical_line_gap = line_gaps[len(line_gaps) // 2]  # Median gap
        else:  # Should not happen if line_gaps was populated
            typical_line_gap = 12.0

    # A new subsection usually has a gap larger than 1.5x typical line gap, or typical + small constant
    subsection_line_gap_threshold = max(typical_line_gap * 1.6, typical_line_gap + 6.0)
    min_threshold = 8.0  # Minimum sensible gap to declare a new subsection
    actual_threshold = max(subsection_line_gap_threshold, min_threshold)

    def check_gap(
        current_line: Line, prev_line: Optional[Line], context_lines: Lines
    ) -> bool:
        if not prev_line or not current_line[0] or not prev_line[0]:
            return False  # Cannot compare if prev_line is None or lines are empty

        # current_line[0].y is top of current line, prev_line[0].y is top of prev line
        # Gap is from top of prev_line to top of current_line (since y increases downwards)
        # Or, more robustly, from bottom of prev_line (y + height) to top of current_line (y)
        # For simplicity, using y difference (top to top) assuming consistent baselines
        gap = current_line[0].y - prev_line[0].y
        return gap > actual_threshold

    return check_gap


def is_line_strong_subsection_header(
    current_line: Line, prev_line: Optional[Line]
) -> bool:
    """
    Checks if the current_line strongly indicates a new subsection header
    (e.g., Job Title, Project Name, School Name).
    """
    if not current_line or not current_line[0]:
        return False
    item = current_line[0]
    text = item.text.strip()

    if not text or not has_letter(item):
        return False  # Must have text with letters
    if BULLET_REGEX.match(text):
        return False  # Bullet points are not headers

    # Characteristic 1: Bold text, not excessively long (e.g., < 7 words)
    if is_bold(item) and len(text.split()) < 7:
        # And previous line was not also bold (or was clearly different like a bullet list)
        if (
            not prev_line
            or not prev_line[0]
            or not is_bold(prev_line[0])
            or (
                prev_line
                and prev_line[0]
                and BULLET_REGEX.match(prev_line[0].text.strip())
            )
        ):
            return True

    # Characteristic 2: Title Case or Starts with Capital, relatively short, not a full sentence
    # For the sample: "Software Engineer Intern", "Research Assistant", "The Designer's Touch"
    if (
        text[0].isupper()
        and len(text.split()) < 7
        and not text.endswith((".", "!", "?"))
    ):
        # If previous line was a bullet point or a full sentence, this is a good candidate
        if prev_line and prev_line[0]:
            prev_text_stripped = prev_line[0].text.strip()
            if BULLET_REGEX.match(prev_text_stripped) or prev_text_stripped.endswith(
                (".", "!", "?")
            ):
                return True
            # Or if prev_line was significantly different (e.g. much longer, or not title-cased itself)
            if (
                len(prev_text_stripped.split()) > 10
                or not prev_text_stripped[0].isupper()
            ):
                return True
        elif (
            not prev_line
        ):  # If it's the first line after a large gap (prev_line would be from prior subsection)
            return True

    # Characteristic 3 (For sample resume): Company Name like "Woafmeow, Inc" might not be bold
    # or "University of Southern Mississippi" under Research Assistant
    if (
        re.match(
            r"^[A-Z][\w\s.,'-]+(?:Inc\.?|LLC|Ltd\.?|University|College|Institute)\b",
            text,
            re.IGNORECASE,
        )
        and len(text.split()) < 7
    ):
        # And previous line was different (e.g. a job title)
        if (
            prev_line and prev_line[0] and is_bold(prev_line[0])
        ):  # e.g. if prev line was a bold job title
            return True
        return True  # Allow if it's a strong company/uni pattern

    return False


def create_subsections(
    lines_in_section: Lines, check_gap_func: IsLineNewSubsectionFunc
) -> Subsections:
    subsections_coll: Subsections = []
    current_subsection_lines: Lines = []

    if not lines_in_section:
        return []

    for i, line_obj in enumerate(lines_in_section):
        if not line_obj:
            continue  # Skip empty lines if they exist

        should_start_new = False
        if i == 0:  # First line always starts a subsection
            current_subsection_lines.append(line_obj)
            continue

        prev_line_obj = None
        for k in range(i - 1, -1, -1):  # Find last non-empty line
            if lines_in_section[k]:
                prev_line_obj = lines_in_section[k]
                break

        # Reason 1: Significant Y-axis gap
        if check_gap_func(line_obj, prev_line_obj, lines_in_section):
            should_start_new = True

        # Reason 2: Formatting suggests a new header, even if gap isn't huge
        if not should_start_new:
            if is_line_strong_subsection_header(line_obj, prev_line_obj):
                should_start_new = True

        if should_start_new:
            if current_subsection_lines:  # Finalize the previous subsection
                subsections_coll.append(list(current_subsection_lines))
            current_subsection_lines = [line_obj]  # Start new one
        else:
            current_subsection_lines.append(line_obj)

    if current_subsection_lines:  # Add the last one
        subsections_coll.append(list(current_subsection_lines))

    return subsections_coll


def divide_section_into_subsections(lines: Lines) -> Subsections:
    if not lines:
        return []

    gap_checker = create_is_line_new_subsection_by_line_gap(lines)
    subsections = create_subsections(lines, gap_checker)

    return [sub for sub in subsections if sub]  # Filter out empty subsections
