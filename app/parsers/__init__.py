from typing import IO
from app.parsers.read_pdf import read_pdf_from_stream
from app.parsers.group_text_items_into_lines import group_text_items_into_lines
from app.parsers.group_lines_into_sections import (
    group_lines_into_sections,
    PROFILE_SECTION,
)
from app.parsers.extract_resume_from_sections.main_extractor import (
    extract_resume_from_sections,
)
from app.models import Resume  # Pydantic model for the final resume
from app.parsers.types import ResumeSectionToLinesMap


def parse_resume_from_pdf_stream(file_stream: IO[bytes]) -> Resume:
    # Step 1. Read pdf
    text_items = read_pdf_from_stream(file_stream)
    if not text_items:
        # Return an empty resume or raise an error
        return Resume()

    # Step 2. Group text items into lines
    lines = group_text_items_into_lines(text_items)
    if not lines:
        return Resume()

    # Step 3. Group lines into sections
    # The ResumeSectionToLinesMap is a Dict[str, Lines]
    sections_map: ResumeSectionToLinesMap = group_lines_into_sections(lines)

    # Ensure profile section exists if it's the only content and wasn't explicitly named
    if not sections_map and lines:  # No sections detected but there are lines
        sections_map[PROFILE_SECTION] = lines
    elif (
        PROFILE_SECTION not in sections_map and lines
    ):  # Profile not explicitly found, but content exists
        # This case might be tricky if other sections were found but not profile.
        # The original TS groupLinesIntoSections initializes with PROFILE_SECTION.
        # Our Python version tries to do something similar.
        # If 'profile' is missing but other sections were found, we assume the initial lines
        # (before any explicit section title) belong to profile if it's the default starting section.
        # This needs to be handled carefully in group_lines_into_sections.
        # For now, assume group_lines_into_sections handles it.
        pass

    # Step 4. Extract resume from sections
    resume_data = extract_resume_from_sections(sections_map)

    return resume_data
