# app/models/extraction_log.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import datetime


class SegmentedSections(BaseModel):
    contact_info_text: Optional[str] = None
    experience_text: Optional[str] = None
    education_text: Optional[str] = None
    skills_text: Optional[str] = None


class ExtractionLog(BaseModel):
    resume_filename: str
    extraction_timestamp: datetime.datetime = Field(
        default_factory=datetime.datetime.now
    )
    file_type_processed: str  # pdf, docx, txt
    cleaned_full_text: Optional[str] = None
    raw_text_pages: Optional[List[str]] = None
    segmented_sections: Optional[SegmentedSections] = None
    extraction_status: str  # success, partial_success, failure
    error_message: Optional[str] = None
    character_count_cleaned: Optional[int] = None
    word_count_cleaned: Optional[int] = None
