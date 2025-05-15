import copy
from typing import TypeVar, Dict, Any, List, Union

T = TypeVar("T", bound=Dict[str, Any])


def cx(*classes: Union[str, bool, None]) -> str:
    """
    Simple util to join classNames together.
    """
    new_classes = []
    for c in classes:
        if isinstance(c, str):
            new_classes.append(c.strip())
    return " ".join(new_classes)


def deep_clone(obj: T) -> T:
    """
    Deep clone utility.
    """
    return copy.deepcopy(obj)


def is_object(item: Any) -> bool:
    return item and isinstance(item, dict)


def deep_merge(
    target: Dict[str, Any], source: Dict[str, Any], level: int = 0
) -> Dict[str, Any]:
    """
    Deep merge two objects by overriding target with fields in source.
    Returns a new object.
    """
    copy_target = copy.deepcopy(target) if level == 0 else target
    for key, source_value in source.items():
        if not is_object(source_value):
            copy_target[key] = source_value
        else:
            if not is_object(copy_target.get(key)):
                copy_target[key] = {}
            deep_merge(copy_target[key], source_value, level + 1)
    return copy_target


# get_px_per_rem is browser-specific, not applicable for backend
# make_object_char_iterator is for UI animation, not applicable for backend parsing
