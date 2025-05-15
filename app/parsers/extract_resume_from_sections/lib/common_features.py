import re
from typing import Callable, List, Tuple
from app.parsers.types import TextItem, FeatureSets  # Use FeatureSets from types.py


def is_text_item_bold(font_name: str) -> bool:
    return (
        "bold" in font_name.lower() or "black" in font_name.lower()
    )  # Adding 'black' as it often implies bold


def is_bold(item: TextItem) -> bool:
    return is_text_item_bold(item.font_name)


def has_letter(item: TextItem) -> bool:
    return bool(re.search(r"[a-zA-Z]", item.text))


def has_number(item: TextItem) -> bool:
    return bool(re.search(r"[0-9]", item.text))


def has_comma(item: TextItem) -> bool:
    return "," in item.text


def get_has_text(text_to_find: str) -> Callable[[TextItem], bool]:
    # Ensure text_to_find is a string, especially if it comes from an earlier extraction
    # that might have returned None or some other type.
    if (
        not isinstance(text_to_find, str) or not text_to_find
    ):  # if text_to_find is empty or not string
        return lambda item: False  # Return a function that always returns False
    return lambda item: text_to_find in item.text


def has_only_letters_spaces_ampersands(item: TextItem) -> bool:
    return bool(re.fullmatch(r"^[A-Za-z\s&]+$", item.text.strip()))


def has_letter_and_is_all_upper_case(item: TextItem) -> bool:
    return has_letter(item) and item.text.upper() == item.text


# Date Features
def has_year(item: TextItem) -> bool:
    return bool(re.search(r"(?:19|20)\d{2}", item.text))


MONTHS = [
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


def has_month(item: TextItem) -> bool:
    return any(month in item.text or month[:4] in item.text for month in MONTHS)


SEASONS = ["Summer", "Fall", "Spring", "Winter"]


def has_season(item: TextItem) -> bool:
    return any(season in item.text for season in SEASONS)


def has_present(item: TextItem) -> bool:
    return "Present" in item.text or "Current" in item.text  # Added "Current"


DATE_FEATURE_SETS: FeatureSets = [
    (has_year, 1),
    (has_month, 1),
    (has_season, 1),
    (has_present, 1),
    (has_comma, -1),
]
