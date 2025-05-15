import re
from typing import Tuple, Dict, Any, Optional
from app.parsers.types import TextItem, FeatureSets, ResumeSectionToLinesMap, TextScores
from app.parsers.extract_resume_from_sections.lib.common_features import (
    is_bold,
    has_number,
    has_comma,
    has_letter,
    has_letter_and_is_all_upper_case,
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.models import ResumeProfile  # For the return type


# Name
def match_only_letter_space_or_period(item: TextItem) -> Optional[re.Match[str]]:
    return re.fullmatch(r"^[a-zA-Z\s\.]+$", item.text.strip())


# Email
def match_email(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"\S+@\S+\.\S+", item.text)  # search, not fullmatch


def has_at(item: TextItem) -> bool:
    return "@" in item.text


# Phone
def match_phone(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}", item.text)


def has_parenthesis(item: TextItem) -> bool:
    return bool(re.search(r"\([0-9]+\)", item.text))


# Location
def match_city_and_state(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(
        r"[A-Z][a-zA-Z\s]+,\s*[A-Z]{2}", item.text
    )  # Added optional space after comma


# Url
def match_url(item: TextItem) -> Optional[re.Match[str]]:
    # More robust: ensure it's not an email
    if "@" in item.text:
        return None
    return re.search(r"\S+\.[a-z]{2,}/\S+", item.text)  # Min 2 chars for TLD


def match_url_http_fallback(item: TextItem) -> Optional[re.Match[str]]:
    if "@" in item.text:
        return None
    return re.search(r"https?:\/\/\S+\.\S+", item.text)


def match_url_www_fallback(item: TextItem) -> Optional[re.Match[str]]:
    if "@" in item.text:
        return None
    return re.search(r"www\.\S+\.\S+", item.text)


def has_slash(item: TextItem) -> bool:
    return "/" in item.text and not "@" in item.text  # Avoid emails with slashes


# Summary
def has_4_or_more_words(item: TextItem) -> bool:
    return len(item.text.split()) >= 4


NAME_FEATURE_SETS: FeatureSets = [
    (match_only_letter_space_or_period, 3, True),
    (is_bold, 2),
    (has_letter_and_is_all_upper_case, 2),
    (has_at, -4),
    (has_number, -4),
    (has_parenthesis, -4),
    (has_comma, -4),
    (has_slash, -4),
    (has_4_or_more_words, -2),
]
EMAIL_FEATURE_SETS: FeatureSets = [
    (match_email, 4, True),
    (is_bold, -1),
    (has_letter_and_is_all_upper_case, -1),
    (has_parenthesis, -4),
    (has_comma, -4),
    (has_slash, -4),
    (has_4_or_more_words, -4),
]
PHONE_FEATURE_SETS: FeatureSets = [
    (match_phone, 4, True),
    (has_letter, -4),
]
LOCATION_FEATURE_SETS: FeatureSets = [
    (match_city_and_state, 4, True),
    (is_bold, -1),
    (has_at, -4),
    (has_parenthesis, -3),
    (has_slash, -4),
]
URL_FEATURE_SETS: FeatureSets = [
    (match_url, 4, True),
    (match_url_http_fallback, 3, True),
    (match_url_www_fallback, 3, True),
    (is_bold, -1),
    (has_at, -4),
    (has_parenthesis, -3),
    (has_comma, -4),
    (has_4_or_more_words, -4),
]
SUMMARY_FEATURE_SETS: FeatureSets = [
    (has_4_or_more_words, 4),
    (is_bold, -1),
    (has_at, -4),
    (has_parenthesis, -3),
    (match_city_and_state, -4, False),  # False, as it's a negative feature here
]


def extract_profile(
    sections: ResumeSectionToLinesMap,
) -> Tuple[ResumeProfile, Dict[str, TextScores]]:
    profile_lines = sections.get(
        "profile", []
    )  # Default to empty list if "profile" key missing
    text_items = [item for sublist in profile_lines for item in sublist]  # Flatten

    name, name_scores = get_text_with_highest_feature_score(
        text_items, NAME_FEATURE_SETS
    )
    email, email_scores = get_text_with_highest_feature_score(
        text_items, EMAIL_FEATURE_SETS
    )
    phone, phone_scores = get_text_with_highest_feature_score(
        text_items, PHONE_FEATURE_SETS
    )
    location, location_scores = get_text_with_highest_feature_score(
        text_items, LOCATION_FEATURE_SETS
    )
    url, url_scores = get_text_with_highest_feature_score(text_items, URL_FEATURE_SETS)
    summary, summary_scores = get_text_with_highest_feature_score(
        text_items, SUMMARY_FEATURE_SETS, True, True
    )  # Concat for summary

    summary_section_lines = get_section_lines_by_keywords(sections, ["summary"])
    summary_section_text = " ".join(
        item.text for line in summary_section_lines for item in line
    ).strip()

    objective_section_lines = get_section_lines_by_keywords(sections, ["objective"])
    objective_section_text = " ".join(
        item.text for line in objective_section_lines for item in line
    ).strip()

    final_summary = summary_section_text or objective_section_text or summary

    profile_data = ResumeProfile(
        name=name,
        email=email,
        phone=phone,
        location=location,
        url=url,
        summary=final_summary,
    )

    # For debugging, similar to original
    profile_scores_debug = {
        "name": name_scores,
        "email": email_scores,
        "phone": phone_scores,
        "location": location_scores,
        "url": url_scores,
        "summary": summary_scores,
    }
    return profile_data, profile_scores_debug
