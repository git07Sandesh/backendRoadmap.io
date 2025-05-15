from typing import (
    List,
    Callable,
    Tuple,
    Union,
    Optional,
    Dict as PyDict,
)  # Renamed Dict to PyDict
import re
from pydantic import BaseModel  # Import BaseModel

# Using Pydantic TextItem from models.py is fine if it serves well.
# For parser-internal use, if TextItem needs more fields or different behavior,
# it could be redefined here. For now, assume app.models.TextItem is used.
from app.models import TextItem

Line = List[TextItem]
Lines = List[Line]
Subsections = List[Lines]


class TextScore(BaseModel):  # Explicitly define here if not in models or if different
    text: str
    score: int
    match: bool


TextScores = List[TextScore]

ResumeKey = str
ResumeSectionToLinesMap = PyDict[ResumeKey, Lines]

# FeatureSet related types
FeatureScoreValue = int
ReturnMatchingTextOnly = bool

FeatureFunctionBool = Callable[[TextItem], bool]
FeatureFunctionMatch = Callable[
    [TextItem], Optional[re.Match[str]]
]  # For regex returning match objects

FeatureSetItemBool = Tuple[FeatureFunctionBool, FeatureScoreValue]
FeatureSetItemMatch = Tuple[
    FeatureFunctionMatch, FeatureScoreValue, ReturnMatchingTextOnly
]

# A FeatureSet is a list of these items
FeatureSetItem = Union[FeatureSetItemBool, FeatureSetItemMatch]
FeatureSets = List[FeatureSetItem]
