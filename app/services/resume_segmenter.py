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
    line_num: int
    span_num: int

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def is_bold(self) -> bool:
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
    "contact": ["contact", "contact information"],  # Often part of profile
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
    # Add more keywords as you discover them from various resumes
}


# --- Step 1: Read text items from a PDF file (Enhanced) ---
def extract_rich_text_items(pdf_file_stream: io.BytesIO) -> List[TextItem]:
    text_items: List[TextItem] = []
    total_spans_processed = 0
    spans_where_text_key_was_usable = 0
    spans_reconstructed_from_chars = 0

    try:
        pdf_file_stream.seek(0)
        doc = fitz.open(stream=pdf_file_stream, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_dict = page.get_text("rawdict", sort=True)

            for block_idx, block in enumerate(page_dict.get("blocks", [])):
                for line_idx_in_block, line_data in enumerate(
                    block.get("lines", [])
                ):  # Renamed to avoid clash
                    for span_idx, span in enumerate(line_data.get("spans", [])):
                        total_spans_processed += 1
                        current_span_text_content = None

                        raw_text_from_text_key = span.get("text")
                        if isinstance(raw_text_from_text_key, str):
                            stripped_text_from_key = raw_text_from_text_key.strip()
                            if stripped_text_from_key:
                                current_span_text_content = stripped_text_from_key
                                spans_where_text_key_was_usable += 1

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
                                    spans_reconstructed_from_chars += 1
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
                                    block_num=block.get("number", block_idx),
                                    line_num=line_idx_in_block,  # Using simple line_idx_in_block
                                    span_num=span_idx,
                                )
                            )
        # print(f"DEBUG: Total spans processed: {total_spans_processed}")
        # print(f"DEBUG: Spans where 'text' key was usable: {spans_where_text_key_was_usable}")
        # print(f"DEBUG: Spans where text was reconstructed from 'chars': {spans_reconstructed_from_chars}")
        # print(f"DEBUG: Extracted {len(text_items)} non-empty rich text items after all checks.")
        # for item_idx, item_val in enumerate(text_items[:10]):
        # print(f"DEBUG Item {item_idx}: {item_val}")
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

    # --- Optional: Debug print for formed lines ---
    # print(f"\nDEBUG GRP_LINES: Total lines formed: {len(lines)}")
    # for i, line_obj in enumerate(lines[:30]): # Print first 30 lines
    #     line_content_str = " | ".join([f"'{item.text}'(b:{item.is_bold}, p:{item.page_num}, y0:{item.y0:.0f})" for item in line_obj])
    #     first_item_y0 = line_obj[0].y0 if line_obj else "N/A"
    #     first_item_page = line_obj[0].page_num if line_obj else "N/A"
    #     print(f"DEBUG GRP_LINES Line {i} (Page {first_item_page}, y0~{first_item_y0}): {line_content_str}")
    return lines


# --- Step 3: Group lines into sections ---
# In app/services/resume_segmenter.py
def is_section_title_heuristic(line_items: Line) -> bool:
    if not line_items:
        # print("DEBUG HEURISTIC: Empty line_items")
        return False

    # --- Add specific debug prints for the target header ---
    # combined_text_for_debug_check = " ".join(item.text for item in line_items).strip().lower()
    # if "work and research experience" in combined_text_for_debug_check:
    #     print(f"\nDEBUG HEURISTIC TRACE for line: '{' '.join(item.text for item in line_items)}'")
    #     print(f"  Number of items on line: {len(line_items)}")
    #     for idx, item_debug in enumerate(line_items):
    #         print(f"  Item {idx}: text='{item_debug.text}', is_bold={item_debug.is_bold}, font_size={item_debug.font_size:.1f}")
    # --- End specific debug ---

    # Allow 1 to 4 items for a potential section header line
    if not (1 <= len(line_items) <= 4):
        # if is_target_header: print(f"  Failed: Item count ({len(line_items)}) not between 1 and 4.")
        return False

    # All items forming the potential header should ideally be bold
    all_items_are_bold = all(item.is_bold for item in line_items)
    if not all_items_are_bold:
        # if is_target_header: print(f"  Failed: Not all items are bold. Bolds: {[item.is_bold for item in line_items]}")
        return False

    # Concatenate text from all items to check overall style
    text_content = " ".join(item.text for item in line_items).strip()

    if not text_content or not any(c.isalpha() for c in text_content):
        # if is_target_header: print(f"  Failed: No alpha text in '{text_content}'")
        return False

    if ":" in text_content:
        parts = text_content.split(":", 1)
        if len(parts) > 1 and parts[1].strip():
            # if is_target_header: print(f"  Failed: Colon with details check for '{text_content}'")
            return False

    is_all_caps = text_content.isupper() and len(text_content) > 1
    is_title_cased = text_content.istitle()
    num_words = len(text_content.split())
    is_plausible_title_case_header = is_title_cased and (
        num_words > 0 and num_words <= 5
    )  # Max 5 words for title case

    # if is_target_header:
    #     print(f"  Combined text: '{text_content}'")
    #     print(f"  is_all_caps: {is_all_caps}")
    #     print(f"  is_title_cased: {is_title_cased}")
    #     print(f"  num_words: {num_words}")
    #     print(f"  is_plausible_title_case_header: {is_plausible_title_case_header}")

    if is_all_caps or is_plausible_title_case_header:
        len_no_space = len(text_content.replace(" ", ""))
        passes_length_check = 2 <= len_no_space <= 50
        passes_exclusion_check = text_content.upper() not in [
            "GPA",
            "USA",
            "MS",
            "BS",
            "PHD",
            "FAQ",
            "DOB",
            "ID",
            "NO",
        ]

        # if is_target_header:
        #     print(f"  case_ok (all_caps or plausible_title_case): {is_all_caps or is_plausible_title_case_header}")
        #     print(f"  passes_length_check ({len_no_space}): {passes_length_check}")
        #     print(f"  passes_exclusion_check: {passes_exclusion_check}")

        if passes_length_check and passes_exclusion_check:
            # if is_target_header: print("  PASSED HEURISTIC!")
            return True

    # if is_target_header: print("  FAILED HEURISTIC (final style/content checks)")
    return False


def find_section_by_keyword(line_text: str) -> Optional[str]:
    normalized_text = line_text.lower().strip()
    # Check for exact matches first or near matches
    for section_category, keywords in COMMON_SECTION_KEYWORDS.items():
        for keyword in keywords:
            if normalized_text == keyword:  # Exact match
                return section_category
            # Check if the line text IS the keyword, ignoring case and spaces for robustness
            if normalized_text.replace(" ", "") == keyword.replace(" ", ""):
                return section_category
    # Then check for startswith (more prone to false positives if not careful)
    for section_category, keywords in COMMON_SECTION_KEYWORDS.items():
        for keyword in keywords:
            if normalized_text.startswith(keyword):
                # Add a length check to avoid matching long sentences that happen to start with a keyword
                if (
                    len(normalized_text) <= len(keyword) + 20
                ):  # Allow some reasonable extra characters
                    return section_category
    return None


# app/services/resume_segmenter.py

# ... (keep TextItem, Line, Lines, ResumeSectionToLines, COMMON_SECTION_KEYWORDS,
#      extract_rich_text_items, group_text_items_into_lines, is_section_title_heuristic,
#      find_section_by_keyword, convert_section_lines_to_text, segment_resume) ...


def group_lines_into_sections(lines: Lines) -> ResumeSectionToLines:
    sections: ResumeSectionToLines = {}
    current_section_title_key = "profile"  # Start with a default section
    current_section_lines: Lines = []

    if not lines:
        # print("DEBUG SECTIONER: No lines to process for section grouping.")
        return {}

    for line_idx, line_items in enumerate(lines):
        if not line_items:
            continue

        line_text_concatenated = " ".join(item.text for item in line_items).strip()
        # ---- Optional: Uncomment for detailed line-by-line processing debug ----
        # print(f"\nDEBUG SECTIONER: Processing Line {line_idx} (p:{line_items[0].page_num} y0~{line_items[0].y0:.0f}): '{line_text_concatenated}'")

        is_stylistic_title_line = is_section_title_heuristic(line_items)
        # print(f"DEBUG SECTIONER: Is Stylistic Title? {is_stylistic_title_line} for line '{line_text_concatenated}'.")

        new_main_section_category: Optional[str] = None
        # Use text of the first item for keyword matching if it's a stylistic title, otherwise whole line
        # This assumes if is_stylistic_title_line is True, line_items[0] is the relevant title text.
        title_text_to_check_keywords = (
            line_items[0].text.strip()
            if is_stylistic_title_line and line_items
            else line_text_concatenated
        )

        if is_stylistic_title_line:
            category_from_main_keywords = find_section_by_keyword(
                title_text_to_check_keywords
            )

            if category_from_main_keywords:
                # It's a stylistic title AND its text matches a known MAIN section keyword.
                # Check if we are in a section like "projects" or "experience" and this match is for a DIFFERENT category.
                # This handles cases like "Research Paper Parser" (stylistic title) matching "research" (for "publications")
                # when we are already in the "projects" section.
                if current_section_title_key in [
                    "projects",
                    "experience",
                ] and category_from_main_keywords not in [
                    "projects",
                    "experience",
                ]:  # Or the specific keyword that defines the current section
                    # print(f"DEBUG SECTIONER: Stylistic Title '{title_text_to_check_keywords}' (matched keyword for '{category_from_main_keywords}') found within '{current_section_title_key}'. Treating as content.")
                    new_main_section_category = (
                        None  # Do NOT start a new main section; it's a sub-item.
                    )
                else:
                    # It's a true new main section based on style and keyword.
                    new_main_section_category = category_from_main_keywords
                    # print(f"DEBUG SECTIONER: Style & Keyword Match (MAIN SECTION): '{title_text_to_check_keywords}' -> New Main Section Category: '{new_main_section_category}'")
                # else:
                # It's a stylistic title (e.g., bold, single item, no colon detail)
                # but its text does NOT match any known main section keyword.
                # e.g., "My Awesome Project Title" (no keywords).
                # If we are in "projects" or "experience", this is likely a sub-item.
                # if current_section_title_key in ["projects", "experience"]:
                #     print(f"DEBUG SECTIONER: Stylistic Title '{title_text_to_check_keywords}' (no main keyword match) found within '{current_section_title_key}'. Treating as content.")
                #     new_main_section_category = None # Treat as content
                # else:
                #     # If not in projects/experience, it might be a custom section header.
                #     # For now, we are stricter: if it's not a known main keyword, it won't start a new section here.
                #     print(f"DEBUG SECTIONER: Stylistic Title '{title_text_to_check_keywords}' (no main keyword match), not in projects/exp. Treating as content for '{current_section_title_key}'.")
                pass  # new_main_section_category remains None, so it's treated as content.

        # Fallback: If not identified as a new main section yet (either not stylistic, or stylistic but decided to be content),
        # check if the whole concatenated line text IS a known main section keyword.
        # This catches headers that might not pass strict style checks but are clear by keyword.
        if not new_main_section_category:
            # Be somewhat restrictive for this fallback to avoid misclassifying content lines.
            if (
                len(line_items) <= 4 and len(line_text_concatenated) < 60
            ):  # Example: "Awards and Honors"
                category_from_fallback = find_section_by_keyword(line_text_concatenated)
                if category_from_fallback:
                    new_main_section_category = category_from_fallback
                    # print(f"DEBUG SECTIONER: Fallback Keyword Matched (MAIN SECTION): '{line_text_concatenated}' -> New Main Section Category: '{new_main_section_category}'")

        # Decision point: Change section or append line
        if (
            new_main_section_category
            and new_main_section_category != current_section_title_key
        ):
            # print(f"DEBUG SECTIONER: New MAIN section identified! Old: '{current_section_title_key}', New: '{new_main_section_category}'. Saving {len(current_section_lines)} lines to '{current_section_title_key}'.")
            if current_section_lines:  # Save previous section's content
                if current_section_title_key not in sections:
                    sections[current_section_title_key] = []
                sections[current_section_title_key].extend(current_section_lines)

            current_section_title_key = (
                new_main_section_category  # Switch to new section
            )
            current_section_lines = []  # Reset lines for the new section
        else:
            # This line is content for the current_section_title_key
            current_section_lines.append(line_items)
            # if new_main_section_category is None and is_stylistic_title_line:
            #     print(f"DEBUG SECTIONER: Appending stylistic non-main title '{title_text_to_check_keywords}' as content to '{current_section_title_key}'")
            # else:
            #     print(f"DEBUG SECTIONER: Appending line as content to '{current_section_title_key}': '{line_text_concatenated}'")

    # Add the last collected section after the loop
    if current_section_lines:
        # print(f"DEBUG SECTIONER: Finalizing. Adding {len(current_section_lines)} lines to last section '{current_section_title_key}'.")
        if current_section_title_key not in sections:
            sections[current_section_title_key] = []
        sections[current_section_title_key].extend(current_section_lines)

    # print(f"DEBUG SECTIONER: Returning sections. Keys: {list(sections.keys())}")
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


# --- Example Usage ---
if __name__ == "__main__":
    # ... (keep example usage for direct testing)
    pass
