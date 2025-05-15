from typing import List, Callable, Tuple, Union, Optional, Any, Pattern, Dict
import re  # For Pattern

# Import main data structures from models.py
from app.models import TextItem, Line, Lines, Subsections, TextScore, TextScores

# Type alias for feature functions and scores
FeatureScore = int  # -4 to 4 in original, but int is fine
ReturnMatchingTextOnly = bool

# A feature can be a function that returns bool, or one that returns a regex match
FeatureFunctionBool = Callable[[TextItem], bool]
FeatureFunctionMatch = Callable[[TextItem], Optional[re.Match[str]]]

FeatureSetItemBool = Tuple[FeatureFunctionBool, FeatureScore]
FeatureSetItemMatch = Tuple[FeatureFunctionMatch, FeatureScore, ReturnMatchingTextOnly]

FeatureSet = Union[FeatureSetItemBool, FeatureSetItemMatch]
FeatureSets = List[
    FeatureSet
]  # Changed from original 'FeatureSet[]' to 'List<FeatureSet>' for clarity

ResumeKey = str  # e.g., "profile", "education", etc.
ResumeSectionToLinesMap = Dict[ResumeKey, Lines]
