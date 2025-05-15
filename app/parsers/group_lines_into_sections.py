import re
from app.parsers.types import Lines, Line, ResumeKey, ResumeSectionToLinesMap
from app.parsers.extract_resume_from_sections.lib.common_features import (
    is_bold,
    has_letter_and_is_all_upper_case,
    has_only_letters_spaces_ampersands,
)

PROFILE_SECTION: ResumeKey = "profile"  # Using a simple string for ResumeKey

SECTION_TITLE_PRIMARY_KEYWORDS = [
    "experience",
    "education",
    "project",
    "skill",
]
SECTION_TITLE_SECONDARY_KEYWORDS = [
    "job",
    "course",
    "extracurricular",
    "objective",
    "summary",
    "award",
    "honor",  # "project" is already primary
]
SECTION_TITLE_KEYWORDS = (
    SECTION_TITLE_PRIMARY_KEYWORDS + SECTION_TITLE_SECONDARY_KEYWORDS
)


def is_section_title(line: Line, line_number: int) -> bool:
    is_first_two_lines = line_number < 2
    has_more_than_one_item_in_line = len(line) > 1
    has_no_item_in_line = len(line) == 0
    if is_first_two_lines or has_more_than_one_item_in_line or has_no_item_in_line:
        return False

    text_item = line[0]
    text_content = text_item.text.strip()

    if is_bold(text_item) and has_letter_and_is_all_upper_case(text_item):
        # Additional check: ensure it's not just a few uppercase acronym, e.g. "GPA"
        # A simple check is if it has at least one space OR is a known section keyword
        if (
            " " in text_content
            or text_content.lower().replace(" ", "") in SECTION_TITLE_KEYWORDS
        ):
            return True

    # Fallback heuristic
    text_has_at_most_2_words = (
        len([word for word in text_content.split(" ") if word != "&"]) <= 2
    )
    starts_with_capital_letter = bool(
        re.match(r"^[A-Z]", text_content)
    )  # Check if first char is capital

    if (
        text_has_at_most_2_words
        and has_only_letters_spaces_ampersands(text_item)
        and starts_with_capital_letter
        and any(keyword in text_content.lower() for keyword in SECTION_TITLE_KEYWORDS)
    ):
        return True

    return False


def group_lines_into_sections(lines: Lines) -> ResumeSectionToLinesMap:
    sections: ResumeSectionToLinesMap = {}
    current_section_name: ResumeKey = PROFILE_SECTION
    current_section_lines: Lines = []

    for i, line in enumerate(lines):
        if not line:
            continue  # Skip empty lines

        # Try to get text of first item, if line is not empty
        # A section title is assumed to be the only item on its line.
        text = line[0].text.strip() if line else ""

        if is_section_title(line, i):
            # Sanitize section name for use as a key (lowercase, replace space with underscore)
            # The original uses the text directly. Let's stick to that for now, but be mindful.
            # For matching logic (e.g. getSectionLinesByKeywords), it's lowercased.

            # Store previous section
            if current_section_name and current_section_lines:  # Ensure there's content
                sections[current_section_name] = list(
                    current_section_lines
                )  # Make a copy

            # Start new section
            current_section_name = text  # Use the detected title as name
            current_section_lines = []
        else:
            current_section_lines.append(line)

    # Add the last section
    if current_section_name and current_section_lines:
        sections[current_section_name] = list(current_section_lines)
    elif (
        not sections.get(PROFILE_SECTION) and current_section_lines
    ):  # If only profile section exists
        sections[PROFILE_SECTION] = list(current_section_lines)

    # Ensure profile section exists, even if empty, if no other sections were found
    # and it's the default.
    if PROFILE_SECTION not in sections and not sections:  # If sections is empty
        sections[PROFILE_SECTION] = (
            current_section_lines  # Add whatever was last collected
        )
    elif PROFILE_SECTION not in sections and current_section_name == PROFILE_SECTION:
        sections[PROFILE_SECTION] = current_section_lines

    return sections
