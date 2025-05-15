from typing import List
from app.parsers.types import Lines, ResumeSectionToLinesMap, ResumeKey


def get_section_lines_by_keywords(
    sections: ResumeSectionToLinesMap, keywords: List[str]
) -> Lines:
    for section_name, section_lines in sections.items():
        # Ensure section_name is a string before calling lower()
        if isinstance(section_name, str):
            if any(keyword.lower() in section_name.lower() for keyword in keywords):
                return section_lines
    return []
