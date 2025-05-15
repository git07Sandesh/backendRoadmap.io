# app/parsers/extract_resume_from_sections/lib/common_features.py
import re
from typing import Callable, List, Tuple
from app.parsers.types import (
    TextItem,
    FeatureSets,
    FeatureSetItem,
)  # Corrected import for FeatureSetItem


def is_text_item_bold(font_name: str) -> bool:
    font_name_lower = font_name.lower()
    # Common bold indicators in font names
    return (
        "bold" in font_name_lower
        or "black" in font_name_lower
        or "heavy" in font_name_lower
        or "demi" in font_name_lower
    )


def is_bold(item: TextItem) -> bool:
    return is_text_item_bold(item.font_name)


def has_letter(item: TextItem) -> bool:
    return bool(re.search(r"[a-zA-Z]", item.text))


def has_number(item: TextItem) -> bool:
    # Be careful: "August 2024" has numbers but is a date component.
    # This function is a general check. Specificity comes from feature scores.
    return bool(re.search(r"\d", item.text))


def has_comma(item: TextItem) -> bool:
    return "," in item.text


def get_has_text(
    text_to_find: str, case_sensitive: bool = False
) -> Callable[[TextItem], bool]:
    if not isinstance(text_to_find, str) or not text_to_find.strip():
        return lambda item: False

    if case_sensitive:
        return lambda item: text_to_find in item.text
    else:
        # Use regex for case-insensitive whole word/phrase matching if possible
        # This simple version checks for substring presence.
        # For robustness, re.escape(text_to_find.lower()) and r'\b' could be used.
        return lambda item: text_to_find.lower() in item.text.lower()


def has_only_letters_spaces_ampersands(item: TextItem) -> bool:
    # Allows hyphens in names too, e.g. "Jean-Luc"
    return bool(re.fullmatch(r"^[A-Za-z\s&\.-]+$", item.text.strip()))


def has_letter_and_is_all_upper_case(item: TextItem) -> bool:
    text_stripped = item.text.strip()
    if not text_stripped or not has_letter(item):
        return False
    # Check if all alphabetic characters are uppercase
    # "GPA: 4.0" -> "GPA" would match, "4.0" would not.
    alpha_chars = "".join(filter(str.isalpha, text_stripped))
    if not alpha_chars:
        return False  # No letters to check case for
    return (
        alpha_chars.isupper() and len(text_stripped) > 1
    )  # Avoid single char unless very specific context


def is_likely_tech_stack(item: TextItem) -> bool:
    text = item.text.lower()
    # Keywords and separators
    tech_keywords = [
        "react",
        "node",
        "python",
        "java",
        "aws",
        "azure",
        "sql",
        "mongo",
        "docker",
        "api",
        "c#",
        ".net",
        "swift",
        "kotlin",
        "angular",
        "spring",
        "django",
        "flask",
        "express",
        "javascript",
        "typescript",
        "html",
        "css",
        "ruby",
        "php",
        "kubernetes",
        "terraform",
        "pandas",
        "numpy",
        "sklearn",
        "tensorflow",
        "pytorch",
        "three.js",
    ]
    # Count occurrences of keywords
    found_count = sum(
        1
        for tech in tech_keywords
        if bool(re.search(r"\b" + re.escape(tech) + r"\b", text))
    )

    # Check for separators like comma, slash, pipe, or multiple keywords
    if (
        text.count(",") >= 1 or text.count("/") >= 1 or text.count("|") >= 1
    ) and found_count >= 1:
        return True
    if found_count >= 2:  # At least two distinct technologies mentioned
        return True
    return False


# Date Features
def has_year(item: TextItem) -> bool:
    # Matches 19XX or 20XX. \b for word boundary to avoid matching parts of longer numbers.
    return bool(re.search(r"\b(?:19|20)\d{2}\b", item.text))


MONTHS_FULL = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTHS_ABBR = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
ALL_MONTHS = MONTHS_FULL + MONTHS_ABBR


def has_month(item: TextItem) -> bool:
    # Case-insensitive search for full month name or abbreviation as a whole word
    return any(
        bool(re.search(r"\b" + month + r"\b", item.text, re.IGNORECASE))
        for month in ALL_MONTHS
    )


SEASONS = ["Summer", "Fall", "Autumn", "Spring", "Winter"]  # Added Autumn


def has_season(item: TextItem) -> bool:
    return any(
        bool(re.search(r"\b" + season + r"\b", item.text, re.IGNORECASE))
        for season in SEASONS
    )


def has_present_or_current(item: TextItem) -> bool:
    return bool(re.search(r"\b(Present|Current)\b", item.text, re.IGNORECASE))


# Date feature sets - used to identify if a text item likely represents a date or part of one.
DATE_FEATURE_SETS: FeatureSets = [
    (has_year, 2),  # Year is a strong indicator
    (has_month, 2),  # Month is also strong
    (has_present_or_current, 3),  # "Present" or "Current" is very indicative
    (has_season, 1),  # Season is a weaker indicator
    (
        lambda item: bool(
            re.search(r"(\b\d{1,2}/\d{4}\b|\b\d{1,2}-\d{4}\b)", item.text)
        ),
        2,
    ),  # MM/YYYY or MM-YYYY
    (
        lambda item: bool(re.search(r"(\b\d{1,2}/\d{1,2}/\d{2,4}\b)", item.text)),
        1,
    ),  # MM/DD/YY(YY)
    (has_comma, -1),  # Commas can appear in dates (May, 2020) but also elsewhere
    (is_likely_tech_stack, -4),  # Dates are not tech stacks
    (
        lambda item: len(item.text.split()) > 5,
        -3,
    ),  # Full dates are usually not very long sentences
]
