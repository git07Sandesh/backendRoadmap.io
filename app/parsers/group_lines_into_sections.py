import re
from app.parsers.types import Lines, Line, ResumeKey, ResumeSectionToLinesMap
from app.parsers.extract_resume_from_sections.lib.common_features import (
    is_bold,
    has_letter_and_is_all_upper_case,  # This needs to be robust
    has_only_letters_spaces_ampersands,
    has_letter,
)

PROFILE_SECTION: ResumeKey = "profile"

SECTION_TITLE_KEYWORDS_ORDERED = [
    "work and research experience",
    "professional experience",
    "work experience",
    "research experience",
    "experience",
    "employment history",
    "education",
    "academic background",
    "projects",
    "personal projects",
    "portfolio",
    "publications",
    "technical skills",
    "skills",
    "competencies",
    "summary",
    "professional summary",
    "career objective",
    "objective",
    "awards and honors",
    "extracurricular activities",
    "volunteer experience",
    "contact",
    "contact information",
]
# Shorter, more generic parts that might appear in titles (used carefully)
SECTION_KEY_FRAGMENTS = [
    "experience",
    "education",
    "project",
    "skill",
    "summary",
    "objective",
    "award",
    "publication",
    "contact",
]


def is_line_a_strong_section_title(line_obj: Line, line_number: int) -> bool:
    if not line_obj or len(line_obj) != 1:  # Title must be the only item on its line
        return False

    text_item = line_obj[0]
    text_content = text_item.text.strip()
    text_lower = text_content.lower()

    if not text_content or not has_letter(text_item):  # Must have letters
        return False

    # Rule 1: Exact or very close match to comprehensive keyword list
    for kw in SECTION_TITLE_KEYWORDS_ORDERED:
        if kw == text_lower:
            return True
        # Allow for title like "EXPERIENCE" to match keyword "experience"
        if (
            text_lower.startswith(kw) and len(text_lower) < len(kw) + 6
        ):  # Slightly longer than keyword
            return True

    # Rule 2: Formatting - Bold AND (All Caps OR Title Case with few words)
    is_all_caps_with_letters = has_letter_and_is_all_upper_case(text_item)
    # Title Case: "Work Experience" - first letter of each word is upper, or "Work experience"
    # A simple check for title case: starts with capital, and if multi-word, subsequent words also often start capital.
    # For simplicity: if it starts with capital and is short.
    is_potential_title_case = (
        text_content[0].isupper() and len(text_content.split()) <= 3
    )

    if is_bold(text_item) and (is_all_caps_with_letters or is_potential_title_case):
        # And it's not excessively long (a single phrase)
        if (
            len(text_content.split()) <= 4 and len(text_content) > 2
        ):  # 1-4 words, >2 chars
            # And it contains some fragment of a known section type, or is a common short title.
            if any(
                frag in text_lower for frag in SECTION_KEY_FRAGMENTS
            ) or text_content.upper() in ["SUMMARY", "OBJECTIVE", "PROFILE", "CONTACT"]:
                return True

    # Rule 3: All Caps (not necessarily bold), short, and contains keyword fragment
    if (
        is_all_caps_with_letters
        and not is_bold(text_item)
        and len(text_content.split()) <= 3
        and len(text_content) > 3
    ):
        if any(frag in text_lower for frag in SECTION_KEY_FRAGMENTS):
            # And not too early in the doc (unless it's "PROFILE" or "CONTACT")
            if line_number > 1 or text_content.upper() in [
                "PROFILE",
                "CONTACT",
                "SUMMARY",
                "OBJECTIVE",
            ]:
                return True

    return False


def group_lines_into_sections(lines: Lines) -> ResumeSectionToLinesMap:
    sections_map: ResumeSectionToLinesMap = {
        PROFILE_SECTION: []
    }  # Initialize profile section
    current_section_key: ResumeKey = PROFILE_SECTION

    if not lines:
        return sections_map

    # Accumulate lines for profile until the first explicit section title is found
    profile_lines_buffer: Lines = []
    first_real_section_found_idx = -1

    for i, line_obj in enumerate(lines):
        if is_line_a_strong_section_title(line_obj, i):
            first_real_section_found_idx = i
            # The lines before this title belong to PROFILE_SECTION
            sections_map[PROFILE_SECTION] = list(
                profile_lines_buffer
            )  # Finalize profile

            # Start the new section
            current_section_key = line_obj[
                0
            ].text.strip()  # Use actual title text as key
            sections_map[current_section_key] = []  # Initialize this new section
            # The title line itself is not part of its content lines
            break  # Exit this initial loop, proceed to process rest
        else:
            if line_obj:  # Add non-empty lines to profile buffer
                profile_lines_buffer.append(line_obj)

    # If no explicit sections were found after profile, all lines belong to profile
    if first_real_section_found_idx == -1:
        sections_map[PROFILE_SECTION] = list(
            profile_lines_buffer
        )  # All lines go to profile
        return sections_map

    # Continue processing from where the first real section title was found
    # The title line itself (at first_real_section_found_idx) is skipped.
    current_lines_for_section: Lines = []
    for i in range(first_real_section_found_idx + 1, len(lines)):
        line_obj = lines[i]
        if is_line_a_strong_section_title(
            line_obj, i
        ):  # Pass 'i' for context if rule needs line_number
            # Store previous section's lines
            if (
                current_section_key in sections_map
            ):  # Should always be true after first section
                sections_map[current_section_key].extend(current_lines_for_section)
            else:  # Should not happen if logic is correct
                sections_map[current_section_key] = list(current_lines_for_section)

            # Start new section
            current_section_key = line_obj[0].text.strip()
            sections_map[current_section_key] = []  # Initialize new section
            current_lines_for_section = []
        else:
            if line_obj:  # Add non-empty lines
                current_lines_for_section.append(line_obj)

    # Add lines for the very last section
    if current_section_key in sections_map:
        sections_map[current_section_key].extend(current_lines_for_section)
    elif current_section_key:  # If it was a new key not yet in map (should be rare)
        sections_map[current_section_key] = list(current_lines_for_section)

    return sections_map
