# app/parsers/extract_resume_from_sections/extract_profile.py
# (Use the refined version from previous response "abandon table parsing...", but with adjustments)
import re
from typing import Tuple, Dict, Any, Optional
from app.parsers.types import TextItem, FeatureSets, ResumeSectionToLinesMap, TextScores
from app.parsers.extract_resume_from_sections.lib.common_features import (
    is_bold,
    has_number,
    has_comma,
    has_letter,
    has_letter_and_is_all_upper_case,
    is_likely_tech_stack,
    has_year_keyword,
)
from app.parsers.extract_resume_from_sections.lib.common_features import (
    has_degree_keyword_heuristic,
    has_school_keyword_heuristic,
)

from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.models import ResumeProfile


# --- Profile Feature Definitions ---
def match_name_heuristic(item: TextItem) -> Optional[re.Match[str]]:
    text = item.text.strip()
    # Usually 2-3 words, first letter of each capitalized.
    if 1 < len(text.split()) <= 4 and all(
        word[0].isupper() for word in text.split() if word
    ):
        if re.fullmatch(r"^[a-zA-Z\s\.'-]+$", text):  # Allows common name chars
            return re.fullmatch(r"^[a-zA-Z\s\.'-]+$", text)
    # Single very prominent name (e.g., all caps, bold)
    if len(text.split()) == 1 and len(text) > 3 and (is_bold(item) or text.isupper()):
        if re.fullmatch(r"^[a-zA-Z'-]+$", text):
            return re.fullmatch(r"^[a-zA-Z'-]+$", text)
    return None


def match_email_address(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", item.text
    )  # Extended TLD


def match_phone_number(item: TextItem) -> Optional[re.Match[str]]:
    # More permissive for various formats
    return re.search(
        r"\(?\+?\d{1,3}\)?[\s.-]?\(?\d{2,5}\)?[\s.-]?\d{2,5}[\s.-]?\d{2,5}(?:[\s.-]?(?:ext|x|)\.?\s*\d{1,5})?",
        item.text,
    )


def match_location_heuristic(item: TextItem) -> Optional[re.Match[str]]:
    # City, ST | City, State | City | Country
    # Avoid matching education/degree lines as location
    text = item.text.strip()
    if has_degree_keyword_heuristic(item) or has_school_keyword_heuristic(item):
        return None
    if (
        has_year_keyword(item)
        or "@" in text
        or "linkedin.com" in text
        or "github" in text
    ):
        return None

    # Common patterns: City, ST | City, Country | City only if few words & capitalized
    if re.search(
        r"\b[A-Z][a-zA-Z\s.-]+,\s*(?:[A-Z]{2}|[A-Za-z\s]+)\b", text
    ):  # City, ST or City, Country
        return re.search(r"\b[A-Z][a-zA-Z\s.-]+,\s*(?:[A-Z]{2}|[A-Za-z\s]+)\b", text)
    if (
        len(text.split(",")) == 1
        and len(text.split()) <= 3
        and text[0].isupper()
        and not any(char.isdigit() for char in text)
    ):  # Just city or country
        return re.match(r"^[A-Z][a-zA-Z\s.-]+$", text)
    return None


def match_linkedin_profile_url(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"linkedin\.com/(?:in|pub)/[\w%/.-]+/?", item.text, re.IGNORECASE)


def match_github_profile_url(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(
        r"(?:github\.com/|github/|[\w-]+\.github\.io/?)(?!.*\.(?:png|jpg|svg))[\w%/.-]*",
        item.text,
        re.IGNORECASE,
    )


def match_other_profile_url(item: TextItem) -> Optional[re.Match[str]]:
    if "@" in item.text or "linkedin.com" in item.text or "github" in item.text:
        return None
    # More general, less specific, looks for domain.tld, possibly with path
    return re.search(
        r"(?:https?://|www\.)?[\w\.-]+\.(?:[a-z]{2,})(?:/[\S]*)?",
        item.text,
        re.IGNORECASE,
    )


def is_profile_summary_candidate(item: TextItem) -> bool:
    text = item.text.strip()
    if not text or len(text.split()) < 5:
        return False  # At least 5 words
    # Not any of the other specific profile fields
    if (
        match_name_heuristic(item)
        or match_email_address(item)
        or match_phone_number(item)
        or match_location_heuristic(item)
        or match_linkedin_profile_url(item)
        or match_github_profile_url(item)
        or has_degree_keyword_heuristic(item)
        or has_school_keyword_heuristic(item)
    ):
        return False
    return True


# Feature Sets
NAME_FS: FeatureSets = [(match_name_heuristic, 5, True), (is_bold, 2)]
EMAIL_FS: FeatureSets = [(match_email_address, 5, True)]
PHONE_FS: FeatureSets = [(match_phone_number, 5, True)]
LOCATION_FS: FeatureSets = [(match_location_heuristic, 4, True)]
URL_FS: FeatureSets = [  # Order matters for prioritization in multi-URL collection
    (match_linkedin_profile_url, 6, True),
    (match_github_profile_url, 5, True),
    (match_other_profile_url, 3, True),
]
SUMMARY_FS: FeatureSets = [
    (is_profile_summary_candidate, 3),
    # Negative scores for things a summary is NOT (especially if these are found in profile lines)
    (has_degree_keyword_heuristic, -5),
    (has_school_keyword_heuristic, -5),
    (is_likely_tech_stack, -4),
    (has_year_keyword, -3),
]


def extract_profile(
    sections: ResumeSectionToLinesMap,
) -> Tuple[ResumeProfile, Dict[str, TextScores]]:
    profile_lines = sections.get("profile", [])
    text_items = [item for sublist in profile_lines for item in sublist]

    name, name_scores = get_text_with_highest_feature_score(text_items, NAME_FS)
    email, email_scores = get_text_with_highest_feature_score(text_items, EMAIL_FS)
    phone, phone_scores = get_text_with_highest_feature_score(text_items, PHONE_FS)
    location, location_scores = get_text_with_highest_feature_score(
        text_items, LOCATION_FS
    )

    # Collect all potential URLs from profile text items
    collected_urls = {}  # Use dict to store URL and its source type for prioritizing
    for item in text_items:
        linkedin_match = match_linkedin_profile_url(item)
        if linkedin_match:
            collected_urls[linkedin_match.group(0).strip()] = "linkedin"

        github_match = match_github_profile_url(item)
        if github_match:
            collected_urls[github_match.group(0).strip()] = "github"

        other_match = match_other_profile_url(item)
        if (
            other_match and other_match.group(0).strip() not in collected_urls
        ):  # Avoid adding if already caught by specific
            collected_urls[other_match.group(0).strip()] = "other"

    # Prioritize and join URLs
    sorted_urls = sorted(
        collected_urls.keys(),
        key=lambda u: (
            (
                0
                if "linkedin" in collected_urls[u]
                else 1 if "github" in collected_urls[u] else 2
            ),
            u,
        ),
    )
    url_string = " | ".join(sorted_urls)
    _, url_scores = get_text_with_highest_feature_score(
        text_items, URL_FS
    )  # For debug scores

    # Summary
    summary_from_section_text = ""
    summary_section_keys = [
        "SUMMARY",
        "summary",
        "OBJECTIVE",
        "objective",
        "Professional Summary",
        "Career Objective",
    ]
    for key in summary_section_keys:
        if key in sections and sections[key]:  # Check if section exists and has lines
            summary_lines = sections[key]
            summary_from_section_text = " ".join(
                item.text for line in summary_lines for item in line
            ).strip()
            if summary_from_section_text:
                break

    summary_from_profile_items = ""
    if not summary_from_section_text and text_items:
        summary_from_profile_items, _ = get_text_with_highest_feature_score(
            text_items,
            SUMMARY_FS,
            return_empty_string_if_highest_score_is_not_positive=True,
            return_concatenated_string_for_texts_with_same_highest_score=True,
        )

    final_summary = summary_from_section_text or summary_from_profile_items
    # Specific cleanup if summary accidentally grabbed degree/school from Sandesh's resume profile block
    if (
        final_summary and not summary_from_section_text
    ):  # Only if summary came from general profile items
        if has_degree_keyword_heuristic(
            TextItem(text=final_summary, x=0, y=0, width=0, height=0, fontName="")
        ) or has_school_keyword_heuristic(
            TextItem(text=final_summary, x=0, y=0, width=0, height=0, fontName="")
        ):
            final_summary = ""

    profile_data = ResumeProfile(
        name=name,
        email=email,
        phone=phone,
        location=location,
        url=url_string,
        summary=final_summary,
    )
    # Simplified debug scores for brevity
    profile_scores_debug = {
        "name": name_scores,
        "email": email_scores,
        "phone": phone_scores,
        "location": location_scores,
        "url": url_scores,
    }
    return profile_data, profile_scores_debug
