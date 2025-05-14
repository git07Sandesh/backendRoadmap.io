# app/services/resume_segmenter.py
import io
import re
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
import fitz  # PyMuPDF


# --- Data Structures ---
@dataclass
class TextItem:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    font_size: float
    font_name: str
    flags: int
    page_num: int
    block_num: int
    line_num: int  # Original line number within block from PyMuPDF
    span_num: int  # Original span number within line from PyMuPDF

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def is_bold(self) -> bool:
        # Flag bit 4 indicates bold
        return bool(self.flags & (1 << 4))

    def __repr__(self):
        return (
            f"TextItem(pg:{self.page_num} text='{self.text[:20]}...' "
            f"y0={self.y0:.0f} x0={self.x0:.0f} bold={self.is_bold} size={self.font_size:.0f})"
        )


Line = List[TextItem]
Lines = List[Line]
ResumeSectionToLines = Dict[str, Lines]

# --- Configuration ---
COMMON_SECTION_KEYWORDS = {
    "profile": [
        "profile",
        "summary",
        "objective",
        "about me",
        "about",
        "personal summary",
        "professional profile",
    ],
    "contact": ["contact", "contact information"],
    "education": [
        "education",
        "academic background",
        "qualifications",
        "academic history",
        "scholastic record",
    ],
    "experience": [
        "experience",
        "work experience",
        "employment history",
        "professional experience",
        "career summary",
        "work history",
        "relevant experience",
        "professional background",
        "career history",
        "internship",
        "internships",
        "work and research experience",
    ],
    "projects": [
        "projects",
        "personal projects",
        "portfolio",
        "technical projects",
        "academic projects",
        "selected projects",
        "project experience",
    ],
    "skills": [
        "skills",
        "technical skills",
        "proficiencies",
        "expertise",
        "technical expertise",
        "technologies",
        "core competencies",
        "technical proficiency",
    ],
    "awards": [
        "awards",
        "honors",
        "achievements",
        "recognitions",
        "scholarships",
        "awards and honors",
        "honors and awards",
    ],
    "publications": [
        "publications",
        "research",
        "articles",
        "conference papers",
        "research and publications",
    ],
    "certifications": [
        "certifications",
        "licenses & certifications",
        "professional certifications",
        "licenses",
        "credentials",
    ],
    "volunteer experience": [
        "volunteer experience",
        "volunteering",
        "community involvement",
        "volunteer work",
        "community service",
    ],
    "languages": ["languages", "language proficiency"],
    "references": ["references"],
    "positions of responsibility": [
        "positions of responsibility",
        "leadership experience",
        "extracurricular activities",
        "activities",
        "leadership roles",
        "leadership",
    ],
}


# --- Step 1: Read text items from a PDF file (Enhanced) ---
def extract_rich_text_items(pdf_file_stream: io.BytesIO) -> List[TextItem]:
    text_items: List[TextItem] = []
    # total_spans_processed = 0 # Uncomment for debug
    # spans_where_text_key_was_usable = 0 # Uncomment for debug
    # spans_reconstructed_from_chars = 0 # Uncomment for debug

    try:
        pdf_file_stream.seek(0)
        doc = fitz.open(stream=pdf_file_stream, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_dict = page.get_text("rawdict", sort=True)

            for block_idx, block in enumerate(page_dict.get("blocks", [])):
                block_num_val = block.get("number", block_idx)
                for line_idx_in_block, line_data in enumerate(block.get("lines", [])):
                    for span_idx, span in enumerate(line_data.get("spans", [])):
                        # total_spans_processed += 1 # Uncomment for debug
                        current_span_text_content = None

                        raw_text_from_text_key = span.get("text")
                        if isinstance(raw_text_from_text_key, str):
                            stripped_text_from_key = raw_text_from_text_key.strip()
                            if stripped_text_from_key:
                                current_span_text_content = stripped_text_from_key
                                # spans_where_text_key_was_usable += 1 # Uncomment for debug

                        if (
                            current_span_text_content is None
                            and "chars" in span
                            and isinstance(span["chars"], list)
                        ):
                            char_list_from_span = []
                            try:
                                for char_info in span["chars"]:
                                    if (
                                        isinstance(char_info, dict)
                                        and "c" in char_info
                                        and isinstance(char_info["c"], str)
                                    ):
                                        char_list_from_span.append(char_info["c"])
                                reconstructed_text = "".join(char_list_from_span)
                                stripped_reconstructed_text = reconstructed_text.strip()
                                if stripped_reconstructed_text:
                                    current_span_text_content = (
                                        stripped_reconstructed_text
                                    )
                                    # spans_reconstructed_from_chars += 1 # Uncomment for debug
                            except Exception as e_char:
                                print(
                                    f"WARNING: Error reconstructing text from chars: {e_char}. Span BBox: {span.get('bbox')}"
                                )

                        if current_span_text_content:
                            text_items.append(
                                TextItem(
                                    text=current_span_text_content,
                                    x0=span.get("bbox", [0, 0, 0, 0])[0],
                                    y0=span.get("bbox", [0, 0, 0, 0])[1],
                                    x1=span.get("bbox", [0, 0, 0, 0])[2],
                                    y1=span.get("bbox", [0, 0, 0, 0])[3],
                                    font_size=span.get("size", 0.0),
                                    font_name=span.get("font", ""),
                                    flags=span.get("flags", 0),
                                    page_num=page_num,
                                    block_num=block_num_val,
                                    line_num=line_idx_in_block,
                                    span_num=span_idx,
                                )
                            )
        return text_items
    except Exception as e:
        print(f"CRITICAL Error in extract_rich_text_items: {e}")
        import traceback

        traceback.print_exc()
        return []
    finally:
        pdf_file_stream.seek(0)


# --- Step 2: Group text items into lines ---
def group_text_items_into_lines(
    text_items: List[TextItem], y_tolerance: float = 2.0
) -> Lines:
    if not text_items:
        return []
    sorted_items = sorted(
        text_items, key=lambda item: (item.page_num, item.y0, item.x0)
    )
    lines: Lines = []
    if not sorted_items:
        return []

    current_line_items: Line = [sorted_items[0]]
    current_page_for_line = sorted_items[0].page_num

    for i in range(1, len(sorted_items)):
        item = sorted_items[i]
        if (
            item.page_num == current_page_for_line
            and abs(item.y0 - current_line_items[0].y0) < y_tolerance
        ):
            current_line_items.append(item)
        else:
            if current_line_items:
                lines.append(sorted(current_line_items, key=lambda it: it.x0))
            current_line_items = [item]
            current_page_for_line = item.page_num

    if current_line_items:
        lines.append(sorted(current_line_items, key=lambda it: it.x0))
    return lines


# --- Step 3: Group lines into sections ---
def is_section_title_heuristic(line_items: Line) -> bool:
    if not line_items:
        return False
    if not (1 <= len(line_items) <= 4):
        return False
    if not all(item.is_bold for item in line_items):
        return False

    combined_text_content = " ".join(item.text for item in line_items).strip()
    if not combined_text_content or not any(c.isalpha() for c in combined_text_content):
        return False
    if ":" in combined_text_content:
        parts = combined_text_content.split(":", 1)
        if len(parts) > 1 and parts[1].strip():
            return False

    is_all_caps = combined_text_content.isupper() and len(combined_text_content) > 1
    is_title_cased = combined_text_content.istitle()
    num_words = len(combined_text_content.split())
    is_plausible_title_case_header = is_title_cased and (
        num_words > 0 and num_words <= 5
    )

    if is_all_caps or is_plausible_title_case_header:
        len_no_space = len(combined_text_content.replace(" ", ""))
        if not (2 <= len_no_space <= 50):
            return False
        if combined_text_content.upper() in [
            "GPA",
            "USA",
            "MS",
            "BS",
            "PHD",
            "FAQ",
            "DOB",
            "ID",
            "NO",
        ]:
            return False
        return True
    return False


def find_section_by_keyword(line_text: str) -> Optional[str]:
    normalized_text = line_text.lower().strip()
    for section_category, keywords in COMMON_SECTION_KEYWORDS.items():
        for keyword in keywords:
            if normalized_text == keyword:
                return section_category
            if normalized_text.replace(" ", "") == keyword.replace(" ", ""):
                return section_category
    for section_category, keywords in COMMON_SECTION_KEYWORDS.items():
        for keyword in keywords:
            if (
                len(keyword) < 4
                and normalized_text.startswith(keyword)
                and normalized_text == keyword
            ):
                return section_category
            elif len(keyword) >= 4 and normalized_text.startswith(keyword):
                if len(normalized_text) <= len(keyword) + 25:
                    return section_category
    return None


def group_lines_into_sections(lines: Lines) -> ResumeSectionToLines:
    sections: ResumeSectionToLines = {}
    current_section_title_key = "profile"
    current_section_lines: Lines = []

    if not lines:
        return {}

    for line_idx, line_items in enumerate(lines):
        if not line_items:
            continue

        line_text_concatenated = " ".join(item.text for item in line_items).strip()
        # ---- Optional: Uncomment for detailed line-by-line processing debug ----
        # print(f"\nDEBUG SECTIONER Line {line_idx} (p{line_items[0].page_num} y{line_items[0].y0:.0f}): '{line_text_concatenated}' | Current: '{current_section_title_key}'")

        is_stylistic_title = is_section_title_heuristic(line_items)
        # if is_stylistic_title: print(f"  Line '{line_text_concatenated}' IS a stylistic title.")
        # else: print(f"  Line '{line_text_concatenated}' is NOT a stylistic title.")

        title_text_for_keyword_check = (
            line_items[0].text.strip()
            if is_stylistic_title and line_items
            else line_text_concatenated
        )

        # This variable will hold the category if this line IS a new main section.
        # If it remains None, the line is treated as content for the current section.
        identified_new_main_section_category: Optional[str] = None

        if is_stylistic_title:
            category_from_keywords_for_stylistic_title = find_section_by_keyword(
                title_text_for_keyword_check
            )

            if category_from_keywords_for_stylistic_title:
                # This stylistic title's text matches a known MAIN section keyword.
                # This is a strong candidate for a new main section, UNLESS it's a suppressed subheading.

                # Suppression condition:
                # If current section is one that expects subheadings (e.g., "projects", "experience")
                # AND the stylistic title's keyword maps to a DIFFERENT main category
                # AND that different category is NOT "profile" (profile can usually break any section)
                is_suppressed_subheading = (
                    current_section_title_key in ["projects", "experience"]
                    and category_from_keywords_for_stylistic_title
                    != current_section_title_key
                    and category_from_keywords_for_stylistic_title != "profile"
                )

                if not is_suppressed_subheading:
                    identified_new_main_section_category = (
                        category_from_keywords_for_stylistic_title
                    )
                # else: # It IS a suppressed subheading (e.g. "Research Paper Parser" in "Projects")
                # print(f"    Stylistic title '{title_text_for_keyword_check}' suppressed as subheading in '{current_section_title_key}'.")
                # identified_new_main_section_category remains None, so it's treated as content.
                # else: # Stylistic title, but its text does NOT match any main section keyword (e.g. "Chatty: A Chat Application")
                # This is treated as content for the current section.
                # print(f"    Stylistic title '{title_text_for_keyword_check}' - no main keyword match. Treating as content.")
                # identified_new_main_section_category remains None.
                pass  # Explicitly do nothing, it's content

        # Fallback: Only if NOT a stylistic title (or if stylistic but decided to be content because no keyword match or suppressed)
        if not identified_new_main_section_category:
            if (
                not is_stylistic_title
            ):  # IMPORTANT: Only apply fallback if the line wasn't already processed as a stylistic title
                if len(line_items) <= 4 and len(line_text_concatenated) < 70:
                    category_from_fallback = find_section_by_keyword(
                        line_text_concatenated
                    )
                    if category_from_fallback:
                        identified_new_main_section_category = category_from_fallback
                        # print(f"    Fallback keyword match for '{line_text_concatenated}' -> {identified_new_main_section_category}")

        # Decision to change section
        if (
            identified_new_main_section_category
            and identified_new_main_section_category != current_section_title_key
        ):
            # print(f"  *** Changing Section from '{current_section_title_key}' to '{identified_new_main_section_category}'. Saving {len(current_section_lines)} lines. ***")
            if current_section_lines:
                sections.setdefault(current_section_title_key, []).extend(
                    current_section_lines
                )
            current_section_title_key = identified_new_main_section_category
            current_section_lines = []
        else:  # Line is content for the current section
            current_section_lines.append(line_items)

    if current_section_lines:  # Add last section
        sections.setdefault(current_section_title_key, []).extend(current_section_lines)

    return sections


# --- Helper & Main Orchestration ---
def convert_section_lines_to_text(section_lines: Lines) -> str:
    output = []
    for line in section_lines:
        output.append(" ".join(item.text for item in line))
    return "\n".join(output)


def segment_resume(
    pdf_file_stream: io.BytesIO,
) -> Tuple[Optional[ResumeSectionToLines], List[TextItem], Lines]:
    text_items = extract_rich_text_items(pdf_file_stream)
    if not text_items:
        return {}, [], []
    lines = group_text_items_into_lines(text_items)
    if not lines:
        return {}, text_items, []
    sections = group_lines_into_sections(lines)
    return sections if sections else {}, text_items, lines
