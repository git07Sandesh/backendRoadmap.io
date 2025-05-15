from typing import List
from app.parsers.types import TextItem, Line, Lines
from app.parsers.extract_resume_from_sections.lib.bullet_points import (
    BULLET_POINTS,
)  # For should_add_space_between_text


# Helper to get typical char width
def get_typical_char_width(text_items: List[TextItem]) -> float:
    text_items_filtered = [item for item in text_items if item.text.strip()]
    if not text_items_filtered:
        return 5.0  # Default small width if no text

    height_to_count = {}
    common_height = 0
    height_max_count = 0

    font_name_to_count = {}
    common_font_name = ""
    font_name_max_count = 0

    for item in text_items_filtered:
        height = round(item.height, 2)  # Round to avoid float precision issues
        height_to_count[height] = height_to_count.get(height, 0) + 1
        if height_to_count[height] > height_max_count:
            common_height = height
            height_max_count = height_to_count[height]

        font_name = item.font_name
        font_name_to_count[font_name] = font_name_to_count.get(font_name, 0) + len(
            item.text
        )
        if font_name_to_count[font_name] > font_name_max_count:
            common_font_name = font_name
            font_name_max_count = font_name_to_count[font_name]

    common_text_items = [
        item
        for item in text_items_filtered
        if item.font_name == common_font_name and round(item.height, 2) == common_height
    ]

    if not common_text_items:  # Fallback if no "common" items found
        common_text_items = text_items_filtered
        if not common_text_items:
            return 5.0

    total_width = sum(item.width for item in common_text_items)
    num_chars = sum(len(item.text) for item in common_text_items)

    return (
        (total_width / num_chars) if num_chars > 0 else 5.0
    )  # Avg char width, default 5.0


def should_add_space_between_text(left_text: str, right_text: str) -> bool:
    if not left_text or not right_text:
        return False
    left_text_end = left_text[-1]
    right_text_start = right_text[0]

    conditions = [
        left_text_end in [":", ",", "|", "."] + BULLET_POINTS
        and right_text_start != " ",
        left_text_end != " " and right_text_start in ["|"] + BULLET_POINTS,
    ]
    return any(conditions)


def group_text_items_into_lines(text_items: List[TextItem]) -> Lines:
    if not text_items:
        return []

    # Sort items by y-coordinate, then x-coordinate to process in reading order
    # This is crucial because PyMuPDF might give spans out of visual order sometimes.
    # Higher Y means lower on page for PyMuPDF.
    # So sort by Y primarily, then X.
    sorted_items = sorted(text_items, key=lambda item: (round(item.y), round(item.x)))

    lines: Lines = []
    if not sorted_items:
        return lines

    current_line: Line = [sorted_items[0]]

    # Group items into lines based on y-coordinate similarity
    # This replaces the `hasEOL` logic from pdfjs-dist
    # A small tolerance for y-coordinate variation within the same line
    Y_TOLERANCE_RATIO = 0.5  # As a ratio of item height

    for i in range(1, len(sorted_items)):
        prev_item = (
            current_line[-1] if current_line else sorted_items[i - 1]
        )  # Fallback if current_line was cleared
        current_item = sorted_items[i]

        # Check if current_item is on the same line as prev_item
        # Using center y of prev_item and comparing with current_item's y range
        prev_item_y_center = prev_item.y + prev_item.height / 2
        y_tolerance = prev_item.height * Y_TOLERANCE_RATIO

        if (
            abs(prev_item_y_center - (current_item.y + current_item.height / 2))
            <= y_tolerance
        ):
            current_line.append(current_item)
        else:
            if current_line:  # Finalize previous line
                # Sort items in the line by x-coordinate to ensure correct order
                current_line.sort(key=lambda item: item.x)
                lines.append(current_line)
            current_line = [current_item]  # Start new line

    if current_line:  # Add the last line
        current_line.sort(key=lambda item: item.x)
        lines.append(current_line)

    # Merge adjacent text items if their distance is small (noise reduction)
    processed_lines: Lines = []
    if not lines:
        return []

    # Calculate typicalCharWidth based on all items for better accuracy.
    # Ensure flat_items only contains non-empty text items.
    flat_items = [item for sublist in lines for item in sublist if item.text.strip()]
    typical_char_width = (
        get_typical_char_width(flat_items) if flat_items else 1.0
    )  # Min width of 1

    for line in lines:
        if not line:
            continue

        # Make a copy to modify while iterating (or build a new line)
        merged_line: Line = []
        if not line:
            continue

        current_merged_item = TextItem(
            **line[0].dict()
        )  # Start with the first item, deep copy

        for i in range(1, len(line)):
            next_item = line[i]

            # Check distance between current_merged_item's end and next_item's start
            gap = next_item.x - (current_merged_item.x + current_merged_item.width)

            if gap <= typical_char_width:  # Merge condition
                if should_add_space_between_text(
                    current_merged_item.text, next_item.text
                ):
                    current_merged_item.text += " "
                current_merged_item.text += next_item.text
                # Update width of current_merged_item
                current_merged_item.width = (
                    next_item.x + next_item.width
                ) - current_merged_item.x
                # Font name: if they differ, this simple merge might lose info.
                # The original TS also merges into leftItem, implicitly taking its font.
                # For simplicity, we do the same. More complex logic could create a new item type.
            else:  # No merge, finalize current_merged_item and start new one
                merged_line.append(current_merged_item)
                current_merged_item = TextItem(**next_item.dict())  # Deep copy

        merged_line.append(current_merged_item)  # Add the last (or only) merged item
        processed_lines.append(merged_line)

    return processed_lines
