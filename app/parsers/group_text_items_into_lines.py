from typing import List
from app.parsers.types import TextItem, Line, Lines
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    BULLET_POINTS_CHARS,
)  # Changed from BULLET_POINTS

Y_LINE_TOLERANCE_ABS = (
    2.0  # Absolute tolerance in points for items to be on the same line (e.g., 2pt)
)


def get_typical_char_width(text_items: List[TextItem]) -> float:
    if not text_items:
        return 5.0
    valid_items = [
        item
        for item in text_items
        if item.text.strip() and item.width > 0 and len(item.text) > 0
    ]
    if not valid_items:
        return 5.0

    total_width = sum(item.width for item in valid_items)
    total_chars = sum(len(item.text) for item in valid_items)
    avg_char_width = (total_width / total_chars) if total_chars > 0 else 5.0

    # Cap width to avoid extremes from very wide/narrow chars or PDF errors
    return min(max(avg_char_width, 2.0), 15.0)


def should_add_space_between_text(left_text: str, right_text: str) -> bool:
    if not left_text or not right_text:
        return False

    left_char = left_text[-1]
    right_char = right_text[0]

    if left_char in [":", ",", "|", "."] + BULLET_POINTS_CHARS and right_char != " ":
        return True
    if left_char != " " and right_char in ["|"] + BULLET_POINTS_CHARS:
        return True
    if (
        left_char.isalnum()
        and right_char.isalnum()
        and left_char != " "
        and right_char != " "
    ):
        return True
    if (
        left_char in [".", ",", ";", ":", "!", "?"]
        and right_char.isalnum()
        and left_char != " "
        and right_char != " "
    ):
        return True
    return False


def group_text_items_into_lines(text_items: List[TextItem]) -> Lines:
    if not text_items:
        return []

    # Items should already be sorted by read_pdf. If not, uncomment:
    # text_items.sort(key=lambda item: (round(item.y), item.x))

    lines_initial_grouping: Lines = []
    if not text_items:
        return []

    current_line_buffer: Line = [text_items[0]]
    for i in range(1, len(text_items)):
        # Use the first item in buffer as reference for line's y, or the prev item for dynamic baseline.
        # Using first item of buffer is more stable against slight y-drifts within a line.
        line_ref_item = current_line_buffer[0]
        current_item = text_items[i]

        # Compare vertical centers or tops. For baselines, y + height would be better.
        # Let's stick to y (top) comparison with absolute tolerance.
        # This assumes items on the same line have very similar y_start coordinates.
        # PyMuPDF bbox y0 is the top of the character.
        if abs(line_ref_item.y - current_item.y) <= Y_LINE_TOLERANCE_ABS:
            current_line_buffer.append(current_item)
        else:
            current_line_buffer.sort(key=lambda item: item.x)
            lines_initial_grouping.append(current_line_buffer)
            current_line_buffer = [current_item]

    if current_line_buffer:
        current_line_buffer.sort(key=lambda item: item.x)
        lines_initial_grouping.append(current_line_buffer)

    merged_lines: Lines = []
    typical_char_width = get_typical_char_width(text_items)

    for line_group in lines_initial_grouping:
        if not line_group:
            continue

        processed_line: Line = []
        current_merged_item_dict = line_group[0].model_dump()

        for i in range(1, len(line_group)):
            next_item = line_group[i]
            gap = next_item.x - (
                current_merged_item_dict["x"] + current_merged_item_dict["width"]
            )

            # Merge if gap is small (typical_char_width or less) or items overlap (negative gap)
            # A slightly larger threshold can help merge closely spaced words.
            # Max merge distance: e.g., 1.5 times typical_char_width. If typical_char_width is small, ensure a min gap.
            max_merge_distance = max(typical_char_width * 1.5, 3.0)  # At least 3 points

            if gap <= max_merge_distance:
                if should_add_space_between_text(
                    current_merged_item_dict["text"], next_item.text
                ):
                    current_merged_item_dict["text"] += " "
                current_merged_item_dict["text"] += next_item.text
                current_merged_item_dict["width"] = (
                    next_item.x + next_item.width
                ) - current_merged_item_dict["x"]
                current_merged_item_dict["height"] = max(
                    current_merged_item_dict["height"], next_item.height
                )
                # If fonts differ, could store a list or take first/dominant. Original keeps first.
                # current_merged_item_dict['fontName'] remains from the first part of merge.
            else:
                processed_line.append(TextItem(**current_merged_item_dict))
                current_merged_item_dict = next_item.model_dump()

        processed_line.append(TextItem(**current_merged_item_dict))
        merged_lines.append(processed_line)

    return [
        line for line in merged_lines if line
    ]  # Filter out any potentially empty lines
