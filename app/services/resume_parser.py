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
from . import detailed_extractor

from ..models.extraction_log import (
    ExtractionLog,
    SegmentedSections,
    WorkExperienceEntry,
    ProjectEntry,
    EducationEntry,
)

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


# --- Original Text Extraction Functions (Defined in THIS file) ---
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


async def process_resume_file_to_log(
    file_stream: io.BytesIO,
    filename: str,
) -> ExtractionLog:
    raw_full_text_content = ""
    raw_text_pages_list: Optional[List[str]] = None
    file_type_processed = ""
    extraction_status = "failure"
    error_message_log = None
    cleaned_full_resume_text = ""
    character_count_cleaned = 0
    word_count_cleaned = 0
    dynamic_segmented_lines_output: Optional[Dict[str, resume_segmenter.Lines]] = None

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
            # VVV CORRECTED CALLS VVV
            raw_full_text_content, raw_text_pages_list = (
                extract_text_from_pdf_fitz_plain(plain_text_stream)
            )
            plain_text_stream.close()
        elif file_type_processed == "docx":
            docx_stream = io.BytesIO(original_file_content)
            raw_full_text_content = extract_text_from_docx(docx_stream)  # CORRECTED
            docx_stream.close()
        elif file_type_processed == "txt":
            txt_stream = io.BytesIO(original_file_content)
            raw_full_text_content = extract_text_from_txt(txt_stream)  # CORRECTED
            txt_stream.close()

        if not raw_full_text_content.strip():
            error_message_log = (
                "Could not extract any text from the file or file is empty."
            )
            raise ValueError(error_message_log)

        cleaned_full_resume_text = clean_text(raw_full_text_content)  # CORRECTED
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
                rich_sections_with_lines, _, _ = resume_segmenter.segment_resume(
                    segmenter_stream
                )

                if rich_sections_with_lines:
                    dynamic_segmented_lines_output = rich_sections_with_lines
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
    segmented_data_for_model = SegmentedSections()

    if dynamic_segmented_lines_output:
        normalized_segmenter_keys = {
            key.lower().replace("_", " ").strip(): lines_list
            for key, lines_list in dynamic_segmented_lines_output.items()
        }

        unmapped_text_sections: Dict[str, str] = {}

        for seg_key_norm, lines_list_val in normalized_segmenter_keys.items():
            section_text_content = resume_segmenter.convert_section_lines_to_text(
                lines_list_val
            )

            if seg_key_norm == "profile" or seg_key_norm == "contact":
                segmented_data_for_model.contact_info_text = (
                    segmented_data_for_model.contact_info_text
                    + f"\n{section_text_content}"
                    if segmented_data_for_model.contact_info_text
                    else section_text_content
                )
            elif seg_key_norm == "summary" or seg_key_norm == "objective":
                segmented_data_for_model.summary_text = (
                    segmented_data_for_model.summary_text + f"\n{section_text_content}"
                    if segmented_data_for_model.summary_text
                    else section_text_content
                )

            elif "experience" in seg_key_norm or seg_key_norm in [
                "work experience",
                "employment history",
                "professional experience",
                "internship",
                "internships",
                "work and research experience",
            ]:
                exp_entries = detailed_extractor.extract_experience_details(
                    lines_list_val
                )
                if exp_entries:
                    segmented_data_for_model.experience_entries.extend(exp_entries)

            elif seg_key_norm == "education" or "academic" in seg_key_norm:
                edu_entries = detailed_extractor.extract_education_details(
                    lines_list_val
                )
                if edu_entries:
                    segmented_data_for_model.education_entries.extend(edu_entries)

            elif (
                "skill" in seg_key_norm
                or "proficienc" in seg_key_norm
                or "expertise" in seg_key_norm
            ):
                segmented_data_for_model.skills_text = (
                    segmented_data_for_model.skills_text + f"\n{section_text_content}"
                    if segmented_data_for_model.skills_text
                    else section_text_content
                )

            elif "project" in seg_key_norm:
                proj_entries = detailed_extractor.extract_project_details(
                    lines_list_val
                )
                if proj_entries:
                    segmented_data_for_model.project_entries.extend(proj_entries)

            elif (
                "award" in seg_key_norm
                or "honor" in seg_key_norm
                or "achievement" in seg_key_norm
            ):
                segmented_data_for_model.awards_text = (
                    segmented_data_for_model.awards_text + f"\n{section_text_content}"
                    if segmented_data_for_model.awards_text
                    else section_text_content
                )

            elif "publication" in seg_key_norm or (
                "research" in seg_key_norm
                and seg_key_norm != "work and research experience"
            ):
                segmented_data_for_model.publications_text = (
                    segmented_data_for_model.publications_text
                    + f"\n{section_text_content}"
                    if segmented_data_for_model.publications_text
                    else section_text_content
                )

            elif (
                "certification" in seg_key_norm
                or "license" in seg_key_norm
                or "credential" in seg_key_norm
            ):
                segmented_data_for_model.certifications_text = (
                    segmented_data_for_model.certifications_text
                    + f"\n{section_text_content}"
                    if segmented_data_for_model.certifications_text
                    else section_text_content
                )

            elif "volunteer" in seg_key_norm or "community" in seg_key_norm:
                segmented_data_for_model.volunteer_experience_text = (
                    segmented_data_for_model.volunteer_experience_text
                    + f"\n{section_text_content}"
                    if segmented_data_for_model.volunteer_experience_text
                    else section_text_content
                )

            elif (
                "positions of responsibility" in seg_key_norm
                or "leadership" in seg_key_norm
                or "activit" in seg_key_norm
            ):
                segmented_data_for_model.positions_of_responsibility_text = (
                    segmented_data_for_model.positions_of_responsibility_text
                    + f"\n{section_text_content}"
                    if segmented_data_for_model.positions_of_responsibility_text
                    else section_text_content
                )

            elif "language" in seg_key_norm:
                segmented_data_for_model.languages_text = (
                    segmented_data_for_model.languages_text
                    + f"\n{section_text_content}"
                    if segmented_data_for_model.languages_text
                    else section_text_content
                )
            else:
                unmapped_text_sections[seg_key_norm] = section_text_content

        if unmapped_text_sections:
            segmented_data_for_model.unmapped_sections = unmapped_text_sections

    log_segments_object = segmented_data_for_model

    if error_message_log and "NLTK resource error" in error_message_log:
        word_count_cleaned = 0

    return ExtractionLog(
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
