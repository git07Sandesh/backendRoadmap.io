# app/services/resume_parser.py

import io
import re
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from spacy.tokens import (
    Doc,
)  # Assuming spacy.tokens.Doc is still relevant for later NLP stages
from typing import List, Optional, Tuple
import unicodedata
import datetime

from ..models.extraction_log import ExtractionLog, SegmentedSections  # New model

# from ..models.resume import ResumeData # Keep if you plan to use ResumeData for advanced parsing output later


def extract_text_from_pdf_fitz(pdf_file_stream: io.BytesIO) -> Tuple[str, List[str]]:
    """Extracts text from a PDF using PyMuPDF (fitz), returning full text and page-wise text."""
    full_text = []
    raw_text_pages = []
    try:
        doc = fitz.open(stream=pdf_file_stream, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            full_text.append(page_text)
            raw_text_pages.append(page_text)
        return "\n".join(full_text), raw_text_pages
    except Exception as e:
        # Log or handle specific fitz exceptions if needed
        raise ValueError(f"Error processing PDF with PyMuPDF: {str(e)}") from e


def extract_text_from_docx(docx_file_stream: io.BytesIO) -> str:
    """Extracts text from a DOCX file."""
    try:
        doc = DocxDocument(docx_file_stream)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        raise ValueError(f"Error processing DOCX: {str(e)}") from e


def extract_text_from_txt(txt_file_stream: io.BytesIO) -> str:
    """Extracts text from a TXT file."""
    try:
        # Assuming UTF-8 encoding, add error handling or detection if needed
        return txt_file_stream.read().decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Error decoding TXT file (ensure UTF-8 encoding): {str(e)}"
        ) from e
    except Exception as e:
        raise ValueError(f"Error processing TXT: {str(e)}") from e


def clean_text(text: str) -> str:
    """Performs basic text cleaning."""
    if not text:
        return ""
    # Normalize Unicode characters to NFKC form
    text = unicodedata.normalize("NFKC", text)
    # Remove non-printable characters (excluding common whitespace like newline, tab, carriage return)
    text = re.sub(
        r"[^\\x20-\\x7E\\n\\r\\t]", "", text
    )  # Keeps ASCII printable and basic whitespace
    # Standardize whitespace: multiple spaces/tabs to a single space, normalize line breaks
    text = re.sub(r"[ \\t]+", " ", text)
    text = re.sub(
        r"\\n+", "\\n", text
    ).strip()  # Normalize newlines and strip leading/trailing whitespace
    # Optional: Handle ligatures if they weren't covered by NFKC or cause issues
    # text = text.replace('ﬁ', 'fi').replace('ﬂ', 'fl') # Example
    return text


# --- Functions for advanced parsing (name, email, phone, skills) can be kept for Phase 2 ---
# def extract_name(nlp_doc: Doc) -> Optional[str]:
# ... (keep existing or refactor for Phase 2)
# def extract_email(text: str) -> Optional[str]:
# ... (keep existing or refactor for Phase 2)
# def extract_phone(text: str) -> Optional[str]:
# ... (keep existing or refactor for Phase 2)
# def extract_skills(nlp_doc: Doc, predefined_skills: Optional[List[str]] = None) -> List[str]:
# ... (keep existing or refactor for Phase 2)


# --- Main processing function for Phase 1 ---
async def process_resume_file_to_log(
    file_stream: io.BytesIO,
    filename: str,
    # nlp_model: Any # nlp_model might not be needed for Phase 1's core objective
) -> ExtractionLog:
    """
    Processes a resume file, extracts text, cleans it, and returns a structured log.
    Focuses on Phase 1 objectives: text extraction and logging.
    """
    raw_full_text = ""
    raw_text_pages_list: Optional[List[str]] = None
    file_type = ""
    status = "failure"
    error_msg = None
    cleaned_text = ""
    char_count = 0
    word_count = 0

    try:
        if filename.lower().endswith(".pdf"):
            file_type = "pdf"
            raw_full_text, raw_text_pages_list = extract_text_from_pdf_fitz(file_stream)
        elif filename.lower().endswith(".docx"):
            file_type = "docx"
            raw_full_text = extract_text_from_docx(file_stream)
        elif filename.lower().endswith(".txt"):
            file_type = "txt"
            raw_full_text = extract_text_from_txt(file_stream)
        else:
            raise ValueError(
                "Unsupported file type. Please upload a PDF, DOCX, or TXT file."
            )

        if not raw_full_text.strip():
            # This case might be considered a partial success if the file was read but empty,
            # or a failure if text extraction truly yielded nothing from a non-empty file.
            status = "failure"  # Or "partial_success"
            error_msg = "Could not extract any text from the file or file is empty."
        else:
            cleaned_text = clean_text(raw_full_text)
            char_count = len(cleaned_text)
            word_count = len(cleaned_text.split())
            status = "success"

    except ValueError as ve:  # Catch specific ValueErrors from extraction/cleaning
        error_msg = str(ve)
        status = "failure"
    except Exception as e:  # Catch any other unexpected errors
        error_msg = f"An unexpected error occurred: {str(e)}"
        status = "failure"
        # Consider logging the full traceback for unexpected errors internally
        print(
            f"Unexpected error processing {filename}: {e}"
        )  # Replace with proper logging

    # For Phase 1, segmented_sections can be None or a very basic attempt if desired.
    # We'll leave it as None for now to focus on core extraction.
    current_segmented_sections = None

    return ExtractionLog(
        resume_filename=filename,
        extraction_timestamp=datetime.datetime.now(
            datetime.timezone.utc
        ),  # Ensure timezone aware
        file_type_processed=file_type if file_type else "unknown",
        cleaned_full_text=cleaned_text if status == "success" else None,
        raw_text_pages=(
            raw_text_pages_list if file_type == "pdf" and status == "success" else None
        ),
        segmented_sections=current_segmented_sections,  # Placeholder for now
        extraction_status=status,
        error_message=error_msg,
        character_count_cleaned=char_count if status == "success" else 0,
        word_count_cleaned=word_count if status == "success" else 0,
    )


# Remove or comment out the old process_resume_file if it's fully replaced
# async def process_resume_file(
# file: io.BytesIO, filename: str, nlp_model: Any
# ) -> ResumeData:
# ... (old code)
