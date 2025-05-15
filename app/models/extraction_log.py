# app/models/extraction_log.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import datetime


class WorkExperienceEntry(BaseModel):
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    dates: Optional[str] = None
    location: Optional[str] = None
    description_lines: List[str] = []


class ProjectEntry(BaseModel):
    project_name: Optional[str] = None
    dates: Optional[str] = None
    technologies_used: List[str] = []
    description_lines: List[str] = []


class EducationEntry(BaseModel):
    institution_name: Optional[str] = None
    degree_name: Optional[str] = None  # e.g., "Bachelor of Science in Computer Science"
    major: Optional[str] = (
        None  # e.g., "Computer Science" (can be extracted from degree_name)
    )
    minor: Optional[str] = None  # e.g., "Mathematics and Data Analysis"
    graduation_date: Optional[str] = None  # e.g., "May 2026", "Dec 2024 (Expected)"
    gpa: Optional[str] = None  # e.g., "4.0", "3.8/4.0"
    location: Optional[str] = None  # e.g., "Hattiesburg, MS"
    relevant_courses: List[str] = []
    honors_awards: List[str] = (
        []
    )  # e.g., "Honors Discovery Scholar", "3x Presidents List"


class SegmentedSections(BaseModel):
    contact_info_text: Optional[str] = None
    summary_text: Optional[str] = None

    experience_entries: List[WorkExperienceEntry] = []
    project_entries: List[ProjectEntry] = []
    education_entries: List[EducationEntry] = []  # <<< CHANGED FROM education_text

    # Keep raw text for other sections or as fallback if structured extraction fails
    skills_text: Optional[str] = None
    awards_text: Optional[str] = None  # General awards, distinct from education honors
    publications_text: Optional[str] = None
    certifications_text: Optional[str] = None
    volunteer_experience_text: Optional[str] = None
    positions_of_responsibility_text: Optional[str] = None
    languages_text: Optional[str] = None

    unmapped_sections: Optional[Dict[str, str]] = None


class ExtractionLog(BaseModel):
    resume_filename: str
    extraction_timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    file_type_processed: str
    cleaned_full_text: Optional[str] = None
    raw_text_pages: Optional[List[str]] = None
    segmented_sections: Optional[SegmentedSections] = None
    extraction_status: str
    error_message: Optional[str] = None
    character_count_cleaned: Optional[int] = None
    word_count_cleaned: Optional[int] = None
