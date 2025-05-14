# app/services/resume_parser.py

import io
import re
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from typing import List, Optional, Tuple, Dict, Any
import unicodedata
import datetime
import nltk
from nltk.tokenize import word_tokenize

# Import for the new segmentation logic
from . import resume_segmenter

from ..models.extraction_log import ExtractionLog, SegmentedSections  # User's model

# Download NLTK data packages if not already downloaded
_NLTK_PACKAGES = [
    ("tokenizers/punkt", "punkt"),
    ("tokenizers/punkt_tab", "punkt_tab"),
    ("taggers/averaged_perceptron_tagger", "averaged_perceptron_tagger"),
    ("taggers/universal_tagset", "universal_tagset"),
    ("chunkers/maxent_ne_chunker", "maxent_ne_chunker"),
    ("corpora/words", "words"),
]

for path, package_id in _NLTK_PACKAGES:
    try:
        nltk.data.find(path)
    except LookupError:
        print(
            f"NLTK package '{package_id}' (resource '{path}') not found. Downloading..."
        )
        try:
            nltk.download(package_id, quiet=False)
            print(f"NLTK package '{package_id}' downloaded successfully.")
        except Exception as download_e:
            print(f"Error downloading NLTK package '{package_id}': {download_e}")
            print("Please try installing it manually via Python interpreter.")
    except Exception as e:
        print(
            f"An unexpected error occurred while checking for NLTK package '{package_id}': {e}"
        )


# --- Original Text Extraction Functions ---
def extract_text_from_pdf_fitz_plain(
    pdf_file_stream: io.BytesIO,
) -> Tuple[str, List[str]]:
    full_text_parts = []
    raw_text_pages = []
    pdf_file_stream.seek(0)
    try:
        doc = fitz.open(stream=pdf_file_stream, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            full_text_parts.append(page_text)
            raw_text_pages.append(page_text)
        return "\n".join(full_text_parts), raw_text_pages
    except Exception as e:
        raise ValueError(
            f"Error processing PDF with PyMuPDF for plain text: {str(e)}"
        ) from e
    finally:
        pdf_file_stream.seek(0)


def extract_text_from_docx(docx_file_stream: io.BytesIO) -> str:
    docx_file_stream.seek(0)
    try:
        doc = DocxDocument(docx_file_stream)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    except Exception as e:
        raise ValueError(f"Error processing DOCX: {str(e)}") from e
    finally:
        docx_file_stream.seek(0)


def extract_text_from_txt(txt_file_stream: io.BytesIO) -> str:
    txt_file_stream.seek(0)
    try:
        return txt_file_stream.read().decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Error decoding TXT file (ensure UTF-8 encoding): {str(e)}"
        ) from e
    except Exception as e:
        raise ValueError(f"Error processing TXT: {str(e)}") from e
    finally:
        txt_file_stream.seek(0)


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(
        r"[^\x20-\x7E\n\r\t]", "", text
    )  # Keep ASCII printable and basic whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", "\n", text).strip()
    return text


# app/services/resume_parser.py
# ... (imports and other functions remain the same) ...


async def process_resume_file_to_log(
    file_stream: io.BytesIO,
    filename: str,
) -> ExtractionLog:
    # ... (initial variable declarations, file reading, basic text extraction - same as response #21) ...
    raw_full_text_content = ""
    raw_text_pages_list: Optional[List[str]] = None
    file_type_processed = ""
    extraction_status = "failure"
    error_message_log = None
    cleaned_full_resume_text = ""
    character_count_cleaned = 0
    word_count_cleaned = 0
    dynamic_segmented_output: Optional[Dict[str, str]] = None

    try:
        original_file_content = file_stream.read()
        file_stream.seek(0)

        if filename.lower().endswith(".pdf"):
            file_type_processed = "pdf"
        elif filename.lower().endswith(".docx"):
            file_type_processed = "docx"
        elif filename.lower().endswith(".txt"):
            file_type_processed = "txt"
        else:
            error_message_log = (
                "Unsupported file type. Please upload a PDF, DOCX, or TXT file."
            )
            raise ValueError(error_message_log)

        if file_type_processed == "pdf":
            plain_text_stream = io.BytesIO(original_file_content)
            raw_full_text_content, raw_text_pages_list = (
                extract_text_from_pdf_fitz_plain(plain_text_stream)
            )
            plain_text_stream.close()
        elif file_type_processed == "docx":
            docx_stream = io.BytesIO(original_file_content)
            raw_full_text_content = extract_text_from_docx(docx_stream)
            docx_stream.close()
        elif file_type_processed == "txt":
            txt_stream = io.BytesIO(original_file_content)
            raw_full_text_content = extract_text_from_txt(txt_stream)
            txt_stream.close()

        if not raw_full_text_content.strip():
            error_message_log = (
                "Could not extract any text from the file or file is empty."
            )
            raise ValueError(error_message_log)

        cleaned_full_resume_text = clean_text(raw_full_text_content)
        character_count_cleaned = len(cleaned_full_resume_text)

        try:
            words = word_tokenize(cleaned_full_resume_text)
            word_count_cleaned = len(words)
            extraction_status = "success"
        except LookupError as nltk_le:
            error_message_log = (
                f"NLTK resource error: {str(nltk_le)}. Word count failed."
            )
            extraction_status = "partial_success"
        except Exception as tokenize_e:
            error_message_log = (
                f"Tokenization error: {str(tokenize_e)}. Word count failed."
            )
            extraction_status = "partial_success"

        if file_type_processed == "pdf":
            segmenter_stream = io.BytesIO(original_file_content)
            try:
                rich_sections, _, _ = resume_segmenter.segment_resume(segmenter_stream)
                # print(f"DEBUG PARSER: Keys from segmenter: {list(rich_sections.keys()) if rich_sections else 'None/Empty'}")

                if rich_sections:
                    dynamic_segmented_output = {}
                    for title, lines_of_text_items in rich_sections.items():
                        section_text = resume_segmenter.convert_section_lines_to_text(
                            lines_of_text_items
                        )
                        dynamic_segmented_output[title] = section_text

                    if extraction_status != "failure":
                        extraction_status = "success"
                    if error_message_log and "NLTK" in error_message_log:
                        error_message_log += " Advanced segmentation also succeeded."
                    elif not error_message_log and extraction_status == "success":
                        error_message_log = None
                else:
                    if extraction_status == "success":
                        extraction_status = "partial_success"
                    current_error = "PDF processed for basic text, but advanced segmentation yielded no sections."
                    if not error_message_log:
                        error_message_log = current_error
                    else:
                        error_message_log += f" Additionally, {current_error.lower()}"
            except Exception as seg_e:
                print(f"Error during PDF segmentation call for {filename}: {seg_e}")
                if extraction_status == "success":
                    extraction_status = "partial_success"
                seg_fail_msg = f"Advanced PDF segmentation process failed: {str(seg_e)}"
                if not error_message_log:
                    error_message_log = seg_fail_msg
                else:
                    error_message_log += f" {seg_fail_msg}"
            finally:
                segmenter_stream.close()
        elif extraction_status == "success" and not error_message_log:
            pass

    except ValueError as ve:
        if not error_message_log:
            error_message_log = str(ve)
        extraction_status = "failure"
    except Exception as e:
        error_message_log = f"An unexpected error occurred in main processing: {str(e)}"
        extraction_status = "failure"
        print(f"Critical unexpected error processing {filename}: {e}")
        import traceback

        traceback.print_exc()

    # --- Map dynamic_segmented_output to the fixed SegmentedSections Pydantic model ---
    mapped_model_data = {
        "contact_info_text": None,
        "summary_text": None,
        "experience_text": None,
        "education_text": None,
        "skills_text": None,
        "projects_text": None,
        "awards_text": None,
        "publications_text": None,
        "certifications_text": None,
        "volunteer_experience_text": None,
        "positions_of_responsibility_text": None,
        "languages_text": None,
        # Ensure this matches ALL fields in your SegmentedSections Pydantic model
    }

    if dynamic_segmented_output:
        normalized_segmenter_output = {
            key.lower().replace("_", " ").strip(): text
            for key, text in dynamic_segmented_output.items()
        }

        # Explicitly define your target Pydantic model field names here for clarity
        pydantic_contact = "contact_info_text"
        pydantic_summary = "summary_text"
        pydantic_experience = "experience_text"
        pydantic_education = "education_text"
        pydantic_skills = "skills_text"
        pydantic_projects = "projects_text"
        pydantic_awards = "awards_text"
        pydantic_publications = "publications_text"
        pydantic_certs = "certifications_text"
        pydantic_volunteer = "volunteer_experience_text"
        pydantic_positions = "positions_of_responsibility_text"
        pydantic_languages = "languages_text"

        # More flexible mapping: iterate through segmenter keys and see if they indicate a target field
        for seg_key_norm, seg_text in normalized_segmenter_output.items():
            mapped_to_field = False
            if seg_key_norm == "profile" or seg_key_norm == "contact":
                mapped_model_data[pydantic_contact] = (
                    mapped_model_data[pydantic_contact] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_contact]
                    else seg_text
                )
                mapped_to_field = True
            if seg_key_norm == "summary" or seg_key_norm == "objective":
                mapped_model_data[pydantic_summary] = (
                    mapped_model_data[pydantic_summary] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_summary]
                    else seg_text
                )
                mapped_to_field = True

            # User's request: "if experience is there then just put it under experience text"
            # This means if any segmenter key *contains* "experience"
            if (
                "experience" in seg_key_norm
            ):  # Check if "experience" is a substring of the segmenter's key
                mapped_model_data[pydantic_experience] = (
                    mapped_model_data[pydantic_experience] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_experience]
                    else seg_text
                )
                mapped_to_field = True
            # Also handle exact matches from COMMON_SECTION_KEYWORDS that map to experience
            elif seg_key_norm in [
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
            ]:
                mapped_model_data[pydantic_experience] = (
                    mapped_model_data[pydantic_experience] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_experience]
                    else seg_text
                )
                mapped_to_field = True

            if seg_key_norm == "education" or "academic" in seg_key_norm:
                mapped_model_data[pydantic_education] = (
                    mapped_model_data[pydantic_education] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_education]
                    else seg_text
                )
                mapped_to_field = True
            if (
                "skill" in seg_key_norm
                or "proficienc" in seg_key_norm
                or "expertise" in seg_key_norm
            ):  # Catches "skills", "technical skills", etc.
                mapped_model_data[pydantic_skills] = (
                    mapped_model_data[pydantic_skills] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_skills]
                    else seg_text
                )
                mapped_to_field = True
            if (
                "project" in seg_key_norm
            ):  # Catches "projects", "personal projects", etc.
                mapped_model_data[pydantic_projects] = (
                    mapped_model_data[pydantic_projects] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_projects]
                    else seg_text
                )
                mapped_to_field = True
            if (
                "award" in seg_key_norm
                or "honor" in seg_key_norm
                or "achievement" in seg_key_norm
            ):
                mapped_model_data[pydantic_awards] = (
                    mapped_model_data[pydantic_awards] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_awards]
                    else seg_text
                )
                mapped_to_field = True
            if (
                "publication" in seg_key_norm or "research" in seg_key_norm
            ):  # Catches "publications", "research paper parser" if it was categorized as 'publications'
                mapped_model_data[pydantic_publications] = (
                    mapped_model_data[pydantic_publications] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_publications]
                    else seg_text
                )
                mapped_to_field = True
            if (
                "certification" in seg_key_norm
                or "license" in seg_key_norm
                or "credential" in seg_key_norm
            ):
                mapped_model_data[pydantic_certs] = (
                    mapped_model_data[pydantic_certs] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_certs]
                    else seg_text
                )
                mapped_to_field = True
            if "volunteer" in seg_key_norm or "community" in seg_key_norm:
                mapped_model_data[pydantic_volunteer] = (
                    mapped_model_data[pydantic_volunteer] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_volunteer]
                    else seg_text
                )
                mapped_to_field = True
            if (
                "positions of responsibility" in seg_key_norm
                or "leadership" in seg_key_norm
                or "activit" in seg_key_norm
            ):  # "activit" for "activities"
                mapped_model_data[pydantic_positions] = (
                    mapped_model_data[pydantic_positions] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_positions]
                    else seg_text
                )
                mapped_to_field = True
            if "language" in seg_key_norm:
                mapped_model_data[pydantic_languages] = (
                    mapped_model_data[pydantic_languages] + f"\n\n---\n\n{seg_text}"
                    if mapped_model_data[pydantic_languages]
                    else seg_text
                )
                mapped_to_field = True

            # if not mapped_to_field:
            #     print(f"INFO: Unmapped section from segmenter: '{seg_key_norm}' with content preview: '{seg_text[:50]}...'")

    log_segments_object = None
    try:
        log_segments_object = SegmentedSections(**mapped_model_data)
    except Exception as pydantic_e:
        print(
            f"Error instantiating SegmentedSections Pydantic model: {pydantic_e}. Data was: {mapped_model_data}"
        )
        log_segments_object = SegmentedSections()
        current_error_msg = "Error structuring segmented data for log."
        if not error_message_log:
            error_message_log = current_error_msg
        else:
            error_message_log += f" {current_error_msg}"
        if extraction_status != "failure":
            extraction_status = "partial_success"

    if error_message_log and "NLTK resource error" in error_message_log:
        word_count_cleaned = 0

    return ExtractionLog(
        # ... (rest of fields are the same)
        resume_filename=filename,
        extraction_timestamp=datetime.datetime.now(datetime.timezone.utc),
        file_type_processed=file_type_processed if file_type_processed else "unknown",
        cleaned_full_text=(
            cleaned_full_resume_text if extraction_status != "failure" else None
        ),
        raw_text_pages=(
            raw_text_pages_list
            if file_type_processed == "pdf" and raw_text_pages_list
            else None
        ),
        segmented_sections=log_segments_object,
        extraction_status=extraction_status,
        error_message=error_message_log,
        character_count_cleaned=(
            character_count_cleaned if extraction_status != "failure" else 0
        ),
        word_count_cleaned=word_count_cleaned,
    )
