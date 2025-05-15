from typing import List, Tuple, Any
from app.parsers.types import (
    TextItem,
    TextScores,
    FeatureSets,
    TextScore,
    FeatureSet,
    FeatureScore,
    ReturnMatchingTextOnly,
    FeatureFunctionBool,
    FeatureFunctionMatch,
)
import re


def compute_feature_scores(
    text_items: List[TextItem], feature_sets: FeatureSets
) -> TextScores:
    text_scores_list: TextScores = [
        TextScore(text=item.text, score=0, match=False) for item in text_items
    ]

    # To handle cases where a regex match extracts a substring, we might need a more flexible way
    # to add new TextScore objects if a feature extracts a part of item.text
    # For now, let's try to map to the original structure as closely as possible
    # The original's textScores.push({ text, score, match: true }); implies adding new entries

    additional_scores: TextScores = []

    for i, text_item in enumerate(text_items):
        item_base_score_obj = text_scores_list[i]

        for feature_set_item in feature_sets:
            has_feature_func = feature_set_item[0]
            score_value: FeatureScore = feature_set_item[1]
            return_matching_text: ReturnMatchingTextOnly = False
            if len(feature_set_item) > 2:
                return_matching_text = feature_set_item[2]  # type: ignore

            result = has_feature_func(
                text_item
            )  # This can be bool or Match object or None

            if result:  # True for bool, or non-None for Match object
                extracted_text_for_score = text_item.text
                is_sub_match = False

                if return_matching_text and isinstance(result, re.Match):
                    extracted_text_for_score = result.group(0)  # Get the matched part
                    if extracted_text_for_score != text_item.text:
                        is_sub_match = True

                if is_sub_match:
                    # Check if this sub_match already exists in additional_scores to consolidate
                    found_in_additional = False
                    for asc_obj in additional_scores:
                        if asc_obj.text == extracted_text_for_score:
                            asc_obj.score += score_value
                            asc_obj.match = (
                                True  # Ensure match is true if any feature set marks it
                            )
                            found_in_additional = True
                            break
                    if not found_in_additional:
                        additional_scores.append(
                            TextScore(
                                text=extracted_text_for_score,
                                score=score_value,
                                match=True,
                            )
                        )
                else:  # Apply score to the original item's score object
                    item_base_score_obj.score += score_value
                    if (
                        return_matching_text
                    ):  # Even if not a sub-match, mark it as a specific match
                        item_base_score_obj.match = True

    text_scores_list.extend(additional_scores)
    return text_scores_list


def get_text_with_highest_feature_score(
    text_items: List[TextItem],
    feature_sets: FeatureSets,
    return_empty_string_if_highest_score_is_not_positive: bool = True,
    return_concatenated_string_for_texts_with_same_highest_score: bool = False,
) -> Tuple[str, TextScores]:

    text_scores = compute_feature_scores(text_items, feature_sets)

    if not text_scores:
        return "", []

    texts_with_highest_feature_score: List[str] = []
    highest_score = -float("inf")

    # First pass: find the highest score among all (original items and sub-matches)
    for ts_obj in text_scores:
        if ts_obj.score > highest_score:
            highest_score = ts_obj.score

    # Second pass: collect all texts that achieved this highest score
    # Prioritize 'match == True' if scores are equal, as per original logic implicitly
    # by pushing new items for sub-matches.

    # Collect items with highest_score, separating matched and non-matched
    highest_score_items_matched: List[str] = []
    highest_score_items_unmatched: List[str] = []

    for ts_obj in text_scores:
        if ts_obj.score == highest_score:
            if ts_obj.match:
                highest_score_items_matched.append(ts_obj.text)
            else:
                highest_score_items_unmatched.append(ts_obj.text)

    # Prefer explicitly matched items
    if highest_score_items_matched:
        texts_with_highest_feature_score = list(
            set(highest_score_items_matched)
        )  # Unique texts
    elif highest_score_items_unmatched:  # Only if no matched items at this score
        texts_with_highest_feature_score = list(set(highest_score_items_unmatched))
    else:  # Should not happen if highest_score was found
        texts_with_highest_feature_score = []

    if return_empty_string_if_highest_score_is_not_positive and highest_score <= 0:
        return "", text_scores

    if not texts_with_highest_feature_score:
        return "", text_scores

    text_output: str
    if not return_concatenated_string_for_texts_with_same_highest_score:
        # The original just takes [0]. Which one depends on iteration order.
        # To make it somewhat deterministic, sort them.
        texts_with_highest_feature_score.sort()
        text_output = (
            texts_with_highest_feature_score[0]
            if texts_with_highest_feature_score
            else ""
        )
    else:
        # Sort before joining for deterministic output
        texts_with_highest_feature_score.sort()
        text_output = " ".join(s.strip() for s in texts_with_highest_feature_score)

    return text_output.strip(), text_scores
