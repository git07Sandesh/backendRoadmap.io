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
    flags: int  # PyMuPDF font flags
    block_num: int
    line_num: int  # Line number within a block (from PyMuPDF block structure)
    span_num: int  # Span number within a line (from PyMuPDF line structure)

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def is_bold(self) -> bool:
        # Flag bit 4 indicates bold
        return bool(self.flags & (1 << 4))

    def __repr__(self):
        return (
            f"TextItem(text='{self.text[:30]}...', x0={self.x0:.1f}, y0={self.y0:.1f}, "
            f"x1={self.x1:.1f}, y1={self.y1:.1f}, bold={self.is_bold}, size={self.font_size:.1f})"
        )


Line = List[TextItem]  # Represents a line composed of one or more TextItems
Lines = List[Line]  # Represents all lines on a page or in a section
ResumeSectionToLines = Dict[str, Lines]  # Maps section titles to their lines

# --- Configuration ---
COMMON_SECTION_KEYWORDS = {
    "profile": ["profile", "summary", "objective", "about me", "about"],
    "education": [
        "education",
        "academic background",
        "qualifications",
        "academic history",
    ],
    "experience": [
        "experience",
        "work experience",
        "employment history",
        "professional experience",
        "career summary",
        "work history",
        "relevant experience",
    ],
    "projects": ["projects", "personal projects", "portfolio", "technical projects"],
    "skills": [
        "skills",
        "technical skills",
        "proficiencies",
        "expertise",
        "technical expertise",
        "technologies",
    ],
    "awards": ["awards", "honors", "achievements", "recognitions", "scholarships"],
    "publications": ["publications", "research", "articles"],
    "references": ["references"],
    "contact": ["contact", "contact information"],
    # Custom/less common but valid
    "volunteer experience": [
        "volunteer experience",
        "volunteering",
        "community involvement",
    ],
    "certifications": [
        "certifications",
        "licenses & certifications",
        "professional certifications",
    ],
    "courses": ["courses", "relevant coursework", "coursework"],
    "languages": ["languages"],
}


# --- Step 1: Read text items from a PDF file (Enhanced) ---
def extract_rich_text_items(pdf_file_stream: io.BytesIO) -> List[TextItem]:
    text_items: List[TextItem] = []
    try:
        pdf_file_stream.seek(0)
        doc = fitz.open(stream=pdf_file_stream, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_dict = page.get_text(
                "rawdict", sort=True
            )  # sort=True sorts by y, then x

            for block in page_dict.get("blocks", []):
                block_num_val = block.get("number", -1)  # Block number if available
                for line_data in block.get("lines", []):
                    # PyMuPDF's "line" in rawdict is a collection of spans that are baseline-aligned.
                    # We will further process these into our "conceptual lines" later.
                    # Here, line_num could be an index within the block.
                    for span_idx, span in enumerate(line_data.get("spans", [])):
                        text_content = span.get("text", "").strip()
                        if (
                            text_content
                        ):  # Only add if there's actual text after stripping
                            text_items.append(
                                TextItem(
                                    text=text_content,
                                    x0=span.get("bbox", [0, 0, 0, 0])[0],
                                    y0=span.get("bbox", [0, 0, 0, 0])[1],
                                    x1=span.get("bbox", [0, 0, 0, 0])[2],
                                    y1=span.get("bbox", [0, 0, 0, 0])[3],
                                    font_size=span.get("size", 0.0),
                                    font_name=span.get("font", ""),
                                    flags=span.get("flags", 0),
                                    block_num=block_num_val,
                                    line_num=span.get(
                                        "line_num", -1
                                    ),  # from rawdict line if available, else placeholder
                                    span_num=span.get(
                                        "span_num", span_idx
                                    ),  # from rawdict span if available, else placeholder
                                )
                            )
        # print(f"DEBUG: Extracted {len(text_items)} non-empty rich text items. First 5:")
        # for item in text_items[:5]:
        # print(f"DEBUG: {item}")
        return text_items
    except Exception as e:
        print(f"Error extracting rich text items: {e}")
        return []
    finally:
        pdf_file_stream.seek(0)


# --- Step 2: Group text items into lines ---
def group_text_items_into_lines(
    text_items: List[TextItem], y_tolerance: float = 3.0
) -> Lines:
    if not text_items:
        return []

    # Ensure text_items are sorted by y0 then x0 for reliable line grouping
    # PyMuPDF's sort=True in get_text("rawdict") should handle this, but an explicit sort here is safer.
    sorted_items = sorted(text_items, key=lambda item: (item.y0, item.x0))

    lines: Lines = []
    current_line_items: Line = []

    for item in sorted_items:
        if not current_line_items:
            current_line_items.append(item)
        else:
            # Check if item belongs to the current line (based on y-coordinate similarity)
            # Using y0 of the first item in current_line for baseline comparison
            if abs(item.y0 - current_line_items[0].y0) < y_tolerance:
                current_line_items.append(item)
            else:
                # New conceptual line starts
                lines.append(
                    sorted(current_line_items, key=lambda it: it.x0)
                )  # Sort items within the line by x0
                current_line_items = [item]

    if current_line_items:  # Add the last collected line
        lines.append(sorted(current_line_items, key=lambda it: it.x0))

    # print(f"DEBUG: Grouped into {len(lines)} conceptual lines. First 3:")
    # for i, line in enumerate(lines[:3]):
    # print(f"DEBUG: Raw Line {i}: {' | '.join(item.text for item in line)}")

    # Optional: Implement merging of very close text items within each conceptual line
    # This part was simplified in previous versions and is complex to get right like OpenResume's avg char width.
    # For now, we'll keep items separate if PyMuPDF gave them as separate spans unless we implement robust merging.
    # The "rawdict" output often gives well-segmented spans already.

    return lines


# --- Step 3: Group lines into sections ---
def is_section_title_heuristic(line_items: Line) -> bool:
    """
    Applies heuristics to detect a section title based on a line of TextItems.
    Main Heuristic (inspired by OpenResume):
    1. The line effectively consists of a single prominent text item (or few closely related ones that form the title).
    2. That prominent text item is bold.
    3. Its text is ALL UPPERCASE OR Title Case (and not too many words for title case).
    """
    if not line_items:
        return False

    # Consider the line as a whole for some checks, and individual items for others.
    # Heuristic 1: Line primarily consists of one or very few items, with specific styling.
    # For simplicity, we'll check the first item if it dominates the line, or if line has few items.

    # If the line is made of a single text item:
    if len(line_items) == 1:
        item = line_items[0]
        text_content = item.text.strip()

        if not text_content or not any(c.isalpha() for c in text_content):
            return False

        is_all_caps = (
            text_content.isupper() and len(text_content) > 1
        )  # Avoid single uppercase letters as titles
        is_title_cased = text_content.istitle()

        # For title case, be a bit stricter, e.g., not too many words.
        is_plausible_title_case_header = is_title_cased and (
            len(text_content.split()) <= 5
        )  # e.g., "Work And Research Experience"

        if item.is_bold and (is_all_caps or is_plausible_title_case_header):
            # Further check: reasonable length for a title
            if 2 <= len(text_content.replace(" ", "")) <= 50:  # Adjusted length
                # Avoid specific known non-headers that might be bold/caps (e.g., "GPA: 4.0")
                if not re.match(r"^(GPA|DOB|ID|NO)[:\s]", text_content.upper()):
                    # print(f"DEBUG: Main Heuristic MATCH (single item) for '{text_content}' (all_caps: {is_all_caps}, title_case: {is_plausible_title_case_header}, bold: {item.is_bold})")
                    return True

    # Heuristic 2: If multiple items on the line, but they are all bold and form a title-like phrase
    # This is more complex. For now, focusing on the single dominant item or keyword match.
    # A simple check: if ALL items on the line are bold and form a short phrase.
    # full_line_text = " ".join(item.text for item in line_items).strip()
    # if all(item.is_bold for item in line_items) and line_items:
    #     if full_line_text.isupper() or (full_line_text.istitle() and len(full_line_text.split()) <= 5) :
    #         if 2 <= len(full_line_text.replace(" ", "")) <= 50:
    #             # print(f"DEBUG: Main Heuristic MATCH (all bold items) for '{full_line_text}'")
    #             return True

    # print(f"DEBUG: Main Heuristic NO MATCH for line: {' '.join(i.text for i in line_items)}")
    return False


def find_section_by_keyword(line_text: str) -> Optional[str]:
    normalized_text = line_text.lower().strip()
    # Prefer longer, more specific keywords first if there's overlap
    # This simple iteration might not do that, but keyword lists can be ordered.
    for section_category, keywords in COMMON_SECTION_KEYWORDS.items():
        for keyword in keywords:
            # Check for near exact match or if line starts with keyword and isn't much longer
            if normalized_text == keyword:
                return section_category
            # Be careful with startswith to avoid partial word matches if not intended
            if normalized_text.startswith(keyword + " ") or normalized_text.startswith(
                keyword + ":"
            ):
                if (
                    len(normalized_text) <= len(keyword) + 25
                ):  # Allow some trailing content
                    return section_category
            # Case for keyword being the whole line (e.g. "SKILLS")
            if normalized_text == keyword.replace(
                " ", ""
            ):  # Match if spaces are the only diff
                return section_category
    return None


def group_lines_into_sections(lines: Lines) -> ResumeSectionToLines:
    sections: ResumeSectionToLines = {}
    current_section_title_key = "profile"  # Default section key
    current_section_lines: Lines = []

    if not lines:
        # print("DEBUG: No lines provided to group_lines_into_sections.")
        return {}

    for line_idx, line_items in enumerate(lines):
        if not line_items:  # Skip empty lines
            continue

        line_text_concatenated = " ".join(item.text for item in line_items).strip()
        # print(f"\nDEBUG Processing Line {line_idx}: '{line_text_concatenated}' (Items: {len(line_items)})")

        is_title_by_main = is_section_title_heuristic(line_items)
        # print(f"DEBUG Main Heuristic Result for line {line_idx}: {is_title_by_main}")

        identified_category_key: Optional[str] = None
        potential_title_text_from_line = (
            line_text_concatenated  # Default to full line text for keyword matching
        )

        if is_title_by_main:
            # If main heuristic matches, use the text of the (usually first/dominant) item as the basis for categorization
            potential_title_text_from_line = line_items[0].text.strip()
            # Try to map the identified title text to a standard category
            identified_category_key = find_section_by_keyword(
                potential_title_text_from_line
            )
            if not identified_category_key:
                # If not in common keywords, use the title text itself (normalized) as the key
                identified_category_key = (
                    potential_title_text_from_line.lower().replace(" ", "_")
                )
            # print(f"DEBUG Main Heuristic Matched. Title text: '{potential_title_text_from_line}', Category: '{identified_category_key}'")
        else:
            # Fallback: Check if the concatenated line text matches any known keywords
            # Be more restrictive here to avoid misclassifying content lines as titles
            if (
                len(line_items) <= 3 and len(line_text_concatenated) < 50
            ):  # Shorter lines, fewer items
                identified_category_key_by_keyword = find_section_by_keyword(
                    line_text_concatenated
                )
                if identified_category_key_by_keyword:
                    identified_category_key = identified_category_key_by_keyword
                    # print(f"DEBUG Fallback Keyword Matched. Line text: '{line_text_concatenated}', Category: '{identified_category_key}'")

        if (
            identified_category_key
            and identified_category_key != current_section_title_key
        ):
            if current_section_lines:  # Save previous section
                if current_section_title_key not in sections:  # Initialize if new
                    sections[current_section_title_key] = []
                sections[current_section_title_key].extend(current_section_lines)

            current_section_title_key = identified_category_key
            current_section_lines = []  # Start new list for the new section
            # Decide whether to include the title line in its own section's content
            # OpenResume suggests section titles take up the entire line and are distinct.
            # Often, we don't add the title line itself to current_section_lines.
            # If the title line IS the content (e.g. a short profile line), it's different.
            # For now, title lines are separators, not content of their own section.
        else:
            current_section_lines.append(line_items)

    # Add the last collected section
    if current_section_lines:
        if current_section_title_key not in sections:
            sections[current_section_title_key] = []
        sections[current_section_title_key].extend(current_section_lines)

    # print(f"DEBUG: Final sections dict before return: { {k: len(v) for k, v in sections.items()} }")
    return sections


# --- Helper to convert Lines of TextItems back to plain text for logging ---
def convert_section_lines_to_text(section_lines: Lines) -> str:
    output = []
    for line in section_lines:
        output.append(" ".join(item.text for item in line))
    return "\n".join(output)


# --- Main segmentation function ---
def segment_resume(
    pdf_file_stream: io.BytesIO,
) -> Tuple[Optional[ResumeSectionToLines], List[TextItem], Lines]:
    # print("DEBUG: Starting segment_resume")
    text_items = extract_rich_text_items(pdf_file_stream)
    if not text_items:
        # print("DEBUG: No rich text items extracted.")
        return {}, [], []  # Return empty dict for sections, and empty lists

    # print(f"DEBUG: Extracted {len(text_items)} text items.")
    lines = group_text_items_into_lines(text_items)
    if not lines:
        # print("DEBUG: No lines formed from text items.")
        return {}, text_items, []  # Return empty dict for sections

    # print(f"DEBUG: Formed {len(lines)} lines.")
    sections = group_lines_into_sections(lines)
    # print(f"DEBUG: Segmented into {len(sections)} sections.")
    # If sections is empty, it means not even a "profile" section with content was made.
    # This implies group_lines_into_sections might have an issue or received no lines.
    return sections if sections else {}, text_items, lines


# --- Example Usage (for testing this module directly) ---
if __name__ == "__main__":
    resume_path = "test_resume.pdf"  # Replace with your test PDF path
    # print(f"Attempting to test with: {resume_path}")
    try:
        with open(resume_path, "rb") as f:
            pdf_stream = io.BytesIO(f.read())

        # Enable print statements inside functions by uncommenting them for detailed debug
        print("Running segmentation test...")
        segmented_data, all_text_items, all_lines = segment_resume(pdf_stream)

        # print("\n--- All Extracted Text Items (first 20) ---")
        # for i, item in enumerate(all_text_items[:20]):
        #     print(f"Item {i}: {item}")

        # print("\n--- All Reconstructed Lines (first 10) ---")
        # for i, line in enumerate(all_lines[:10]):
        #     line_text = " | ".join(f"'{item.text}'(b:{item.is_bold},s:{item.font_size:.0f})" for item in line)
        #     if line: # Print y0 of the first item for line position reference
        #         print(f"Line {i} (y0~{line[0].y0:.0f}): {line_text}")
        #     else:
        #         print(f"Line {i}: (empty line)")

        print("\n--- Segmented Sections ---")
        if segmented_data:  # An empty dict {} is falsy
            for section_title, section_lines in segmented_data.items():
                print(
                    f"\n== Section: {section_title.upper()} ({len(section_lines)} lines) =="
                )
                for line_idx, line_items_in_section in enumerate(
                    section_lines[:5]
                ):  # Print first 5 lines of section
                    print(
                        f"  L{line_idx}: {' '.join(item.text for item in line_items_in_section)}"
                    )
                if len(section_lines) > 5:
                    print("  ...")
        else:
            print(
                "Could not segment the resume into any sections, or no content found in sections."
            )

    except FileNotFoundError:
        print(
            f"Test file not found: {resume_path}. Please add a PDF resume for testing."
        )
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        import traceback

        traceback.print_exc()
