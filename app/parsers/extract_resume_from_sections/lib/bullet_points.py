import re
from typing import List, Optional
from app.parsers.types import Lines, TextItem, Line

# Unicode bullet points from the original
BULLET_POINTS = [
    "⋅",
    "∙",
    "🞄",
    "•",
    "⦁",
    "⚫︎",
    "●",
    "⬤",
    "⚬",
    "○",
]


def get_bullet_points_from_lines(lines: Lines) -> List[str]:
    if not lines:
        return []

    first_bullet_point_line_idx = get_first_bullet_point_line_idx(lines)
    if first_bullet_point_line_idx is None:
        return [" ".join(item.text for item in line).strip() for line in lines if line]

    line_str = ""
    for item in [item for sublist in lines for item in sublist]:  # Flatten lines
        text = item.text
        if (
            line_str
            and not line_str.endswith(" ")
            and text
            and not text.startswith(" ")
        ):
            line_str += " "
        line_str += text

    line_str = line_str.strip()
    if not line_str:
        return []

    common_bullet_point = get_most_common_bullet_point(line_str)

    first_bullet_point_idx = line_str.find(common_bullet_point)
    if first_bullet_point_idx != -1:
        line_str = line_str[first_bullet_point_idx:]

    # Split by the common bullet point. Need to handle empty strings from multiple bullets.
    # Using re.split to capture the delimiter for more robust splitting around it.
    # However, simpler string split is closer to original if bullet points are single chars.
    if common_bullet_point:  # Ensure common_bullet_point is not empty
        # Escape the bullet point if it's a special regex character
        # For now, assuming they are not, but for robustness:
        # escaped_bullet = re.escape(common_bullet_point)
        # descriptions = [s.strip() for s in re.split(f'({escaped_bullet})', line_str) if s.strip() and s != common_bullet_point]
        # Simpler split, closer to original:
        descriptions = [
            text.strip() for text in line_str.split(common_bullet_point) if text.strip()
        ]

    else:  # No common bullet point found, treat as plain text lines
        descriptions = [line_str]

    return [desc for desc in descriptions if desc]


def get_most_common_bullet_point(text: str) -> str:
    bullet_to_count = {bullet: 0 for bullet in BULLET_POINTS}
    bullet_with_most_count = BULLET_POINTS[0] if BULLET_POINTS else ""
    bullet_max_count = 0

    for (
        char_or_seq
    ) in BULLET_POINTS:  # Check for multi-character bullet points (less common)
        count = text.count(char_or_seq)
        if count > 0:
            bullet_to_count[char_or_seq] = count  # Store actual count
            if count > bullet_max_count:
                bullet_max_count = count
                bullet_with_most_count = char_or_seq

    # Fallback for single character check if no multi-char bullet points were found,
    # or if BULLET_POINTS are all single characters.
    # The above loop already handles single characters correctly if they are in BULLET_POINTS list.

    return bullet_with_most_count if bullet_max_count > 0 else ""


def get_first_bullet_point_line_idx(lines: Lines) -> Optional[int]:
    for i, line in enumerate(lines):
        for item in line:
            if any(bullet in item.text for bullet in BULLET_POINTS):
                return i
    return None


def is_word(s: str) -> bool:
    return bool(re.match(r"^[^0-9]+$", s))


def has_at_least_8_words(item: TextItem) -> bool:
    return len([word for word in re.split(r"\s+", item.text) if is_word(word)]) >= 8


def get_descriptions_line_idx(lines: Lines) -> Optional[int]:
    idx = get_first_bullet_point_line_idx(lines)

    if idx is None:
        for i, line in enumerate(lines):
            if len(line) == 1 and has_at_least_8_words(line[0]):
                idx = i
                break
    return idx
