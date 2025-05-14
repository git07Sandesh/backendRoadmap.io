# app/models/extraction_log.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import datetime


class SegmentedSections(BaseModel):
    contact_info_text: Optional[str] = None
    summary_text: Optional[str] = None  # Could be separate from profile/contact
    experience_text: Optional[str] = None
    education_text: Optional[str] = None
    skills_text: Optional[str] = None
    projects_text: Optional[str] = None
    awards_text: Optional[str] = None
    publications_text: Optional[str] = None
    certifications_text: Optional[str] = None
    volunteer_experience_text: Optional[str] = None
    positions_of_responsibility_text: Optional[str] = None
    languages_text: Optional[str] = None
    # Add any other specific section fields you need


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
