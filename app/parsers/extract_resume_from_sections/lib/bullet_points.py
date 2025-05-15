import re
from typing import List, Optional
from app.parsers.types import Lines, TextItem, Line

# Unicode bullet points from the original
BULLET_POINTS_CHARS = [
    "•",
    "",
    "‣",
    "⁃",
    "◦",
    "▪",
    "▫",
    "∙",
    "⋅",
    "➢",
    "❖",
    "",
    "*",
    "-",
]  # Added more common ones, including asterisk and hyphen
# Regex to match these, allowing optional space after. Hyphen needs care to not match "word-word".
# For hyphen as bullet: it must be at the start of the text item, followed by a space.
HYPHEN_BULLET_REGEX = r"^\s*-\s+"
# Other bullets can be anywhere in the first few chars.
OTHER_BULLETS_REGEX_PART = "|".join(
    re.escape(b) for b in BULLET_POINTS_CHARS if b != "-"
)
BULLET_REGEX = re.compile(
    rf"(?:{HYPHEN_BULLET_REGEX}|^\s*(?:{OTHER_BULLETS_REGEX_PART}))"
)


def get_most_common_bullet_point_sequence(text_block: str) -> str:
    """Finds the most common bullet point sequence (char + optional space) in a block of text."""
    counts = {}
    most_common_bullet_seq = ""
    max_count = 0

    lines = text_block.splitlines()
    for line in lines:
        line_stripped = line.lstrip()  # Remove leading whitespace
        # Check for hyphen bullet first
        if re.match(HYPHEN_BULLET_REGEX, line_stripped):
            match = re.match(HYPHEN_BULLET_REGEX, line_stripped)
            bullet_seq = match.group(0)  # The hyphen and following space(s)
            counts[bullet_seq] = counts.get(bullet_seq, 0) + 1
            if counts[bullet_seq] > max_count:
                max_count = counts[bullet_seq]
                most_common_bullet_seq = bullet_seq
            continue  # Processed this line

        # Check for other bullet characters
        for bp_char in BULLET_POINTS_CHARS:
            if bp_char == "-":
                continue  # Handled by HYPHEN_BULLET_REGEX
            if line_stripped.startswith(bp_char):
                # Consider the bullet char and an optional following space as the sequence
                bullet_seq = bp_char
                if (
                    len(line_stripped) > len(bp_char)
                    and line_stripped[len(bp_char)] == " "
                ):
                    bullet_seq += " "

                counts[bullet_seq] = counts.get(bullet_seq, 0) + 1
                if counts[bullet_seq] > max_count:
                    max_count = counts[bullet_seq]
                    most_common_bullet_seq = bullet_seq
                break  # Found bullet for this line

    return most_common_bullet_seq if max_count > 0 else ""


def get_bullet_points_from_lines(lines: Lines) -> List[str]:
    if not lines:
        return []

    # Flatten all text items into a single string block for analysis, preserving line structure somewhat
    # by joining items within a line first, then joining lines.
    line_strings = [
        " ".join(item.text.strip() for item in line_obj).strip()
        for line_obj in lines
        if line_obj
    ]
    full_text_block = "\n".join(line_strings)

    if not full_text_block.strip():
        return []

    first_bullet_char_line_idx = get_first_bullet_point_line_idx(lines)

    # If no explicit bullet characters are found, but lines are short and numerous (like a list)
    # treat each line as a description item (original behavior for this case).
    if first_bullet_char_line_idx is None:
        # And if it's not just a single long paragraph treated as multiple lines.
        # A simple check: if average line length is short.
        avg_line_len = (
            sum(len(s) for s in line_strings) / len(line_strings) if line_strings else 0
        )
        if (
            len(line_strings) > 1 and avg_line_len < 100
        ):  # Heuristic for "list-like" structure
            return [s for s in line_strings if s]  # Return non-empty lines
        else:  # Otherwise, it's probably a paragraph, return as one item (or split by actual sentences if needed)
            return [full_text_block] if full_text_block else []

    # If bullet characters are present, use them for splitting
    common_bullet_sequence = get_most_common_bullet_point_sequence(full_text_block)

    if (
        not common_bullet_sequence
    ):  # Fallback if sequence detection fails but bullets exist
        # Return lines starting from the first detected bullet, stripping any leading bullets
        descriptions = []
        processing_bullets = False
        for line_str in line_strings:
            match = BULLET_REGEX.match(line_str)
            if match:
                processing_bullets = True
                descriptions.append(line_str[match.end() :].strip())
            elif (
                processing_bullets
            ):  # If current line has no bullet but previous did, append to last
                if descriptions:
                    descriptions[-1] += " " + line_str.strip()
                else:  # Should not happen if processing_bullets is true
                    descriptions.append(line_str.strip())
            # If not processing_bullets yet and no match, skip (it's before the first bullet)
        return [d for d in descriptions if d]

    # Split the full text block by the most common bullet sequence.
    # Using re.split to handle the sequence as a delimiter.
    # Escape the sequence for regex if it contains special characters.
    # The sequence itself already includes trailing space if that's common.
    split_parts = re.split(r"\n?" + re.escape(common_bullet_sequence), full_text_block)

    # The first part before the first bullet might be empty or pre-bullet text.
    # We are interested in parts *after* a bullet.
    descriptions = [
        part.strip().replace("\n", " ") for part in split_parts if part.strip()
    ]

    # If the very first line started with a bullet, re.split might produce an initial empty string.
    # If full_text_block starts with common_bullet_sequence, the first element of split_parts will be empty.
    # Example: "• item1 \n• item2" split by "• " -> ["", "item1 \n", "item2"]
    if (
        full_text_block.lstrip().startswith(common_bullet_sequence)
        and split_parts
        and split_parts[0].strip() == ""
    ):
        return [d for d in descriptions if d]  # Already good
    elif (
        descriptions
        and common_bullet_sequence
        and not full_text_block.lstrip().startswith(common_bullet_sequence)
    ):
        # If first description doesn't start with a bullet, it might be pre-bullet text, remove it
        # UNLESS it was the only thing (meaning no bullets really found by split)
        # This logic is tricky. The goal is to get only text that FOLLOWS a bullet.
        # A simpler approach: iterate lines, if line starts with bullet, take rest of line.
        # Let's refine using line_strings and common_bullet_sequence:
        refined_descriptions = []
        current_desc_parts = []
        for line_str in line_strings:
            stripped_line = line_str.lstrip()
            if stripped_line.startswith(common_bullet_sequence):
                if current_desc_parts:  # Finalize previous description
                    refined_descriptions.append(" ".join(current_desc_parts).strip())
                    current_desc_parts = []
                current_desc_parts.append(
                    stripped_line[len(common_bullet_sequence) :].strip()
                )
            elif current_desc_parts:  # Continuation of current bullet point
                current_desc_parts.append(line_str.strip())
        if current_desc_parts:  # Add last description
            refined_descriptions.append(" ".join(current_desc_parts).strip())

        return [d for d in refined_descriptions if d]

    return [d for d in descriptions if d]  # Fallback if refinement didn't yield results


def get_first_bullet_point_line_idx(lines: Lines) -> Optional[int]:
    for i, line_obj in enumerate(lines):
        if line_obj and line_obj[0]:  # Ensure line and item exist
            # Check if the first text item in the line starts with a bullet pattern
            if BULLET_REGEX.match(line_obj[0].text.lstrip()):
                return i
    return None


def has_at_least_N_words(item: TextItem, n: int) -> bool:
    # Consider words as sequences of alphanumeric characters
    return len(re.findall(r"\b\w+\b", item.text)) >= n


def get_descriptions_line_idx(lines: Lines) -> Optional[int]:
    """
    Tries to find the starting line index of a list of descriptions (e.g., bullet points).
    Favors explicit bullet points. Falls back to checking for long text if no bullets.
    """
    # Main heuristic: explicit bullet points
    bullet_start_idx = get_first_bullet_point_line_idx(lines)
    if bullet_start_idx is not None:
        return bullet_start_idx

    # Fallback: if no bullets, check for a line that seems like the start of a paragraph of details.
    # This is less reliable. The original TS used "hasAtLeast8Words".
    # This might be too aggressive if, e.g., a job title line is long.
    # This fallback should ideally only apply if the preceding lines are clearly headers (short, bold).
    # For now, let's keep it simple and aligned with the original idea.
    for i, line_obj in enumerate(lines):
        if line_obj and len(line_obj) == 1:  # Single text item on the line
            if has_at_least_N_words(line_obj[0], 8):
                # And previous line was not also long (to avoid breaking mid-paragraph)
                if (
                    i > 0
                    and lines[i - 1]
                    and len(lines[i - 1]) == 1
                    and has_at_least_N_words(lines[i - 1][0], 8)
                ):
                    continue  # It's a continuation of long text
                return i  # Found a potential start of a descriptive paragraph
    return None  # No clear start of descriptions found
