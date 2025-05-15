# app/parsers/extract_resume_from_sections/lib/common_features.py
import re
from typing import (
    Callable,
    List,
    Tuple,
    Optional,
)  # Ensure List, Tuple are imported if used for FeatureSets
from app.parsers.types import TextItem, FeatureSets, FeatureSetItem

SCHOOL_KEYWORDS = [
    "College",
    "University",
    "Institute",
    "School",
    "Academy",
    "High School",
]


def has_school_keyword_heuristic(item: TextItem) -> bool:
    text_lower = item.text.lower()
    if re.search(
        r"\b(University|College|Institute|Academy|School)\s+(of|at|in)\b",
        text_lower,
        re.IGNORECASE,
    ):
        return True
    return any(
        bool(re.search(r"\b" + school.lower() + r"\b", text_lower))
        for school in SCHOOL_KEYWORDS
    )


DEGREE_KEYWORDS_HEURISTIC = [
    "Bachelor",
    "Master",
    "PhD",
    "Ph\.D\.",
    "Doctor of",
    "Associate",
    "Diploma",
    "Certificate",
    "B\.S\.",
    "M\.S\.",
    "B\.A\.",
    "M\.A\.",
    "M\.B\.A\.",
    "B\.Eng\.",
    "M\.Eng\.",
    "BSc",
    "MSc",
    "BA",
    "MA",
    "MBA",
    "BEng",
    "MEng",
]


def has_degree_keyword_heuristic(item: TextItem) -> bool:
    text_content = item.text
    if re.search(
        r"\b(Degree|Major|Minor|Concentration)\s+in\b", text_content, re.IGNORECASE
    ):
        return True
    return any(
        bool(re.search(r"\b" + pattern + r"(?:\b|\s|,|$)", text_content, re.IGNORECASE))
        for pattern in DEGREE_KEYWORDS_HEURISTIC
    )


# ... (is_bold, has_letter, has_number, has_comma, get_has_text, has_only_letters_spaces_ampersands, has_letter_and_is_all_upper_case, is_likely_tech_stack remain largely the same from previous refinement)
# Ensure they are robust. For example:
def is_text_item_bold(font_name: str) -> bool:
    font_name_lower = font_name.lower()
    return (
        "bold" in font_name_lower
        or "black" in font_name_lower
        or "heavy" in font_name_lower
        or "demi" in font_name_lower
        or "semibold" in font_name_lower
    )


def is_bold(item: TextItem) -> bool:
    return is_text_item_bold(item.font_name)


def has_letter(item: TextItem) -> bool:
    return bool(re.search(r"[a-zA-Z]", item.text))


def has_number(item: TextItem) -> bool:
    return bool(re.search(r"\d", item.text))


def has_comma(item: TextItem) -> bool:
    return "," in item.text


def get_has_text(
    text_to_find: str, case_sensitive: bool = False
) -> Callable[[TextItem], bool]:
    if not isinstance(text_to_find, str) or not text_to_find.strip():
        return lambda item: False

    pattern = re.escape(text_to_find)
    flags = 0 if case_sensitive else re.IGNORECASE
    # Match as whole word/phrase if it's not too short and seems like a standalone entity
    if (
        len(text_to_find.split()) >= 1 and len(text_to_find) > 2
    ):  # Arbitrary length check
        pattern = r"\b" + pattern + r"\b"

    try:
        regex = re.compile(pattern, flags)
        return lambda item: bool(regex.search(item.text))
    except (
        re.error
    ):  # Fallback for invalid regex patterns, though re.escape should prevent most.
        return lambda item: (
            (text_to_find in item.text)
            if case_sensitive
            else (text_to_find.lower() in item.text.lower())
        )


def has_only_letters_spaces_ampersands(item: TextItem) -> bool:
    return bool(
        re.fullmatch(r"^[A-Za-z\s&\.'-]+$", item.text.strip())
    )  # Added apostrophe and period


def has_letter_and_is_all_upper_case(item: TextItem) -> bool:
    text_stripped = item.text.strip()
    if not text_stripped or not has_letter(item):
        return False
    alpha_chars = "".join(filter(str.isalpha, text_stripped))
    if not alpha_chars:
        return False
    return alpha_chars.isupper() and len(alpha_chars) > 1  # Check length of alpha_chars


def is_likely_tech_stack(item: TextItem) -> bool:
    text = item.text.lower()
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
        "fastapi",
        "sqlalchemy",
    ]
    found_count = sum(
        1
        for tech in tech_keywords
        if bool(re.search(r"\b" + re.escape(tech) + r"\b", text))
    )

    if (
        text.count(",") >= 1
        or text.count("/") >= 1
        or text.count("|") >= 1
        or " & " in text
    ) and found_count >= 1:
        return True
    if found_count >= 2:
        return True
    return False


# --- Date Features (Refined) ---
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
    "Sept",
    "Oct",
    "Nov",
    "Dec",
]  # Added Sept
ALL_MONTHS = MONTHS_FULL + MONTHS_ABBR


def has_month_keyword(item: TextItem) -> bool:
    return any(
        bool(re.search(r"\b" + month + r"\b", item.text, re.IGNORECASE))
        for month in ALL_MONTHS
    )


def has_year_keyword(item: TextItem) -> bool:
    return bool(re.search(r"\b(19\d{2}|20\d{2})\b", item.text))  # Whole word years


def has_present_or_current_keyword(item: TextItem) -> bool:
    return bool(
        re.search(r"\b(Present|Current|Ongoing)\b", item.text, re.IGNORECASE)
    )  # Added Ongoing


# Specific date patterns
def match_date_range_pattern(item: TextItem) -> Optional[re.Match[str]]:
    # Catches "Aug 2024 – Present", "May 2024 - Dec 2024", "Jan 2020 - Mar 2020"
    # Month Year - Month Year | Month Year - Present
    month_pattern = r"(?:" + "|".join(ALL_MONTHS) + r")"
    year_pattern = r"(?:19\d{2}|20\d{2})"
    present_pattern = r"(?:Present|Current|Ongoing)"

    # Pattern: (Month Year) to (Month Year | Present)
    pattern1 = rf"\b{month_pattern}\s+{year_pattern}\s*[-–—to]+\s*(?:{month_pattern}\s+{year_pattern}|{present_pattern})\b"
    # Pattern: (Month - Month Year) e.g. Jan - Mar 2023 (less common but possible)
    # pattern2 = rf"\b{month_pattern}\s*[-–—to]+\s*{month_pattern}\s+{year_pattern}\b"
    # Pattern: (Year - Year) e.g., 2020-2021
    pattern3 = rf"\b{year_pattern}\s*[-–—to]+\s*{year_pattern}\b"
    # Pattern: (Month Year) alone, or just Year (for graduation)
    pattern4 = rf"\b(?:{month_pattern}\s+)?{year_pattern}\b"

    # Try more specific patterns first
    for p_str in [pattern1, pattern3, pattern4]:
        match = re.search(p_str, item.text, re.IGNORECASE)
        if match:
            return match
    return None


# Feature to identify things that are NOT dates, like company names
def is_likely_organization_name(item: TextItem) -> bool:
    text = item.text.strip()
    if not text:
        return False
    # Common suffixes and patterns
    if re.search(
        r"\b(Inc\.?|LLC|Ltd\.?|Corp\.?|University|College|Institute|Foundation|Group|Technologies|Solutions)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    # Starts with capital, multiple words, not too long, doesn't look like a person's name
    if (
        text[0].isupper()
        and 1 < len(text.split()) < 6
        and not match_date_range_pattern(item)
        and not has_month_keyword(item)
    ):
        # Avoid things that look like person names (e.g. "John Doe")
        if (
            len(text.split()) == 2
            and text.split()[0][0].isupper()
            and text.split()[1][0].isupper()
            and not any(c.islower() for c in text.split()[0])
            and not any(c.islower() for c in text.split()[1])
        ):
            # Could be a name like "JOHN DOE", but less likely if it's an org
            pass  # Allow for now, let feature scoring handle overlap
        return True
    return False


DATE_FEATURE_SETS: FeatureSets = [
    (
        match_date_range_pattern,
        5,
        True,
    ),  # Specific date range patterns are high confidence
    (has_present_or_current_keyword, 3),  # "Present" is a strong signal
    (has_month_keyword, 2),
    (has_year_keyword, 2),
    (lambda item: bool(re.search(r"^\d{4}$", item.text.strip())), 1),  # Just a year
    # Negative features
    (is_likely_organization_name, -4),
    (is_likely_tech_stack, -4),
    (
        lambda item: len(item.text.split()) > 7,
        -3,
    ),  # Dates are usually not very long phrases
    (
        lambda item: item.text.count(",") > 1,
        -2,
    ),  # Multiple commas unlikely in a single date string
]
