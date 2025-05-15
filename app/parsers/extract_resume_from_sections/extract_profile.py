import re
from typing import Tuple, Dict, Any, Optional
from app.parsers.types import TextItem, FeatureSets, ResumeSectionToLinesMap, TextScores
from app.parsers.extract_resume_from_sections.lib.common_features import (
    is_bold,
    has_number,
    has_comma,
    has_letter,
    has_letter_and_is_all_upper_case,
    is_likely_tech_stack,  # Import new feature
)
from app.parsers.extract_resume_from_sections.lib.feature_scoring_system import (
    get_text_with_highest_feature_score,
)
from app.parsers.extract_resume_from_sections.lib.get_section_lines import (
    get_section_lines_by_keywords,
)
from app.models import ResumeProfile


# Name
def match_only_letter_space_or_period(item: TextItem) -> Optional[re.Match[str]]:
    # Should be at least two words or a single word if it's long enough and all caps
    text = item.text.strip()
    if " " in text or (len(text) > 5 and text.isupper()):
        return re.fullmatch(r"^[a-zA-Z\s\.]+$", text)
    return None


# Email
def match_email(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", item.text)


def has_at(item: TextItem) -> bool:
    return "@" in item.text


# Phone
def match_phone(item: TextItem) -> Optional[re.Match[str]]:
    # Allow more variations, including international prefixes or extensions
    return re.search(
        r"\(?\+?\d{1,3}\)?[\s.-]?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?:[\s.-]?ext\.?\s*\d+)?",
        item.text,
    )


def has_parenthesis(item: TextItem) -> bool:
    return bool(re.search(r"\([0-9]+\)", item.text))


# Location
def match_city_and_state(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"\b[A-Z][a-zA-Z\s.-]+,\s*[A-Z]{2}\b", item.text)


# Url
def match_linkedin_url(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"linkedin\.com/in/[\w-]+/?", item.text, re.IGNORECASE)


def match_github_url(item: TextItem) -> Optional[re.Match[str]]:
    return re.search(r"github\.(?:com|io)/[\w-]+/?", item.text, re.IGNORECASE)


def match_general_url(item: TextItem) -> Optional[re.Match[str]]:
    # Avoid matching email addresses
    if "@" in item.text:
        return None
    # Basic http/https/www, or domain.tld/path
    return re.search(
        r"(?:https?://|www\.)[\w\.-]+(?:\.[\w])[\w\.-]*(?:/\S*)?|[\w\.-]+\.(?:com|org|net|io|dev|me|tech|ai|co|us)(?:/\S*)?",
        item.text,
        re.IGNORECASE,
    )


def has_slash(item: TextItem) -> bool:
    return "/" in item.text and not "@" in item.text


# Summary
def has_4_or_more_words(item: TextItem) -> bool:
    return len(item.text.split()) >= 4


NAME_FEATURE_SETS: FeatureSets = [
    (match_only_letter_space_or_period, 3, True),
    (is_bold, 2),
    (has_letter_and_is_all_upper_case, 2),
    (has_at, -4),
    (match_phone, -4, False),
    (has_parenthesis, -4),  # Use match_phone here
    (has_comma, -2),  # Name can have comma for suffixes, but penalize slightly
    (has_slash, -4),
    (has_4_or_more_words, -2),
    (is_likely_tech_stack, -4),
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
    (match_linkedin_url, 5, True),  # Prioritize LinkedIn
    (match_github_url, 5, True),  # Prioritize GitHub
    (match_general_url, 3, True),
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
    (match_city_and_state, -4, False),
    (is_likely_tech_stack, -4),
]


def extract_profile(
    sections: ResumeSectionToLinesMap,
) -> Tuple[ResumeProfile, Dict[str, TextScores]]:
    profile_lines = sections.get("profile", [])
    # The name and contact info are usually at the very top, before any explicit section titles.
    # So, if "profile" section is empty, consider the first few lines of the whole resume.
    # This part is tricky; for now, assume `group_lines_into_sections` correctly populates 'profile'.

    text_items = [item for sublist in profile_lines for item in sublist]

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

    # For URLs, we might have multiple. Let's try to find all good ones.
    # The current `getTextWithHighestFeatureScore` returns only one.
    # A temporary workaround: run it multiple times, excluding previously found items.
    # This is complex. For now, let's see if the improved regex helps get at least one.
    url, url_scores = get_text_with_highest_feature_score(text_items, URL_FEATURE_SETS)

    # If multiple URLs are on separate lines and score similarly, we might need to combine them.
    # Example: Check if 'url' is just one and try to find another if the first one was LinkedIn.
    all_urls = []
    if url:
        all_urls.append(url)

    # Try to find a second URL if the first one was LinkedIn and there are other candidates
    if "linkedin.com" in url.lower():
        remaining_items_for_url = [ti for ti in text_items if url not in ti.text]
        if remaining_items_for_url:
            second_url, _ = get_text_with_highest_feature_score(
                remaining_items_for_url, URL_FEATURE_SETS
            )
            if (
                second_url
                and "linkedin.com" not in second_url.lower()
                and second_url not in all_urls
            ):
                all_urls.append(second_url)

    final_url_string = " | ".join(all_urls) if all_urls else ""

    summary, summary_scores = get_text_with_highest_feature_score(
        text_items, SUMMARY_FEATURE_SETS, True, True
    )

    summary_section_lines = get_section_lines_by_keywords(
        sections, ["summary", "objective"]
    )  # Combined
    summary_section_text = " ".join(
        item.text for line in summary_section_lines for item in line
    ).strip()

    objective_section_lines = get_section_lines_by_keywords(
        sections, ["objective"]
    )  # Already handled if combined
    objective_section_text = " ".join(
        item.text for line in objective_section_lines for item in line
    ).strip()

    final_summary = summary_section_text or objective_section_text or summary

    profile_data = ResumeProfile(
        name=name,
        email=email,
        phone=phone,
        location=location,
        url=final_url_string,
        summary=final_summary,
    )

    profile_scores_debug = {
        "name": name_scores,
        "email": email_scores,
        "phone": phone_scores,
        "location": location_scores,
        "url": url_scores,
        "summary": summary_scores,
    }
    return profile_data, profile_scores_debug
