from typing import List, Tuple, Any
from app.parsers.types import (
    TextItem,
    TextScores,
    FeatureSets,
    TextScore,
    FeatureSetItem,
    FeatureScoreValue,
    ReturnMatchingTextOnly,
)
import re


def compute_feature_scores(
    text_items: List[TextItem], feature_sets: FeatureSets
) -> TextScores:
    # Initialize scores for each original text_item
    # We will create new TextScore objects for sub-matches later.
    item_to_base_score_obj: Dict[int, TextScore] = {
        i: TextScore(text=text_items[i].text, score=0, match=False)
        for i in range(len(text_items))
    }

    # Store scores for texts that are sub-matches from regex features
    sub_match_scores: Dict[str, TextScore] = {}

    for i, text_item in enumerate(text_items):
        base_score_obj = item_to_base_score_obj[i]

        for feature_set_item_union in feature_sets:
            # Unpack the feature set item
            has_feature_func = feature_set_item_union[0]
            score_value: FeatureScoreValue = feature_set_item_union[1]
            return_matching_text: ReturnMatchingTextOnly = False
            if len(feature_set_item_union) == 3:  # It's a FeatureSetItemMatch
                return_matching_text = feature_set_item_union[2]  # type: ignore

            result = has_feature_func(text_item)  # bool or Match object or None

            if result:  # True for bool, or non-None for Match object
                extracted_text_for_score = text_item.text
                is_sub_match = False

                if (
                    return_matching_text
                    and isinstance(result, re.Match)
                    and result.group(0)
                ):
                    # Ensure group(0) is not None, though re.Match implies it matched something
                    extracted_text_for_score = result.group(0)
                    if extracted_text_for_score != text_item.text:
                        is_sub_match = True

                if is_sub_match:
                    if extracted_text_for_score not in sub_match_scores:
                        sub_match_scores[extracted_text_for_score] = TextScore(
                            text=extracted_text_for_score,
                            score=0,
                            match=True,  # Always true for sub_matches
                        )
                    sub_match_scores[extracted_text_for_score].score += score_value
                else:  # Apply score to the original item's score object
                    base_score_obj.score += score_value
                    if (
                        return_matching_text
                    ):  # Mark if a regex feature (even full match) was intended
                        base_score_obj.match = True

    final_scores_list: TextScores = list(item_to_base_score_obj.values()) + list(
        sub_match_scores.values()
    )
    return final_scores_list


def get_text_with_highest_feature_score(
    text_items: List[TextItem],
    feature_sets: FeatureSets,
    return_empty_string_if_highest_score_is_not_positive: bool = True,
    return_concatenated_string_for_texts_with_same_highest_score: bool = False,
) -> Tuple[
    str, TextScores
]:  # Return extracted text and all computed scores for debugging

    if not text_items:  # Handle empty input
        return "", []

    text_scores_computed = compute_feature_scores(text_items, feature_sets)

    if not text_scores_computed:
        return "", []

    # Find the highest score achieved
    highest_score_val = -float("inf")
    for ts_obj in text_scores_computed:
        if ts_obj.score > highest_score_val:
            highest_score_val = ts_obj.score

    # Collect all texts that achieved this highest score
    # Prioritize items where `match == True` (i.e., specific regex matches)
    candidates_at_highest_score_matched: List[str] = []
    candidates_at_highest_score_unmatched: List[str] = []

    for ts_obj in text_scores_computed:
        if ts_obj.score == highest_score_val:
            if ts_obj.match:
                candidates_at_highest_score_matched.append(ts_obj.text)
            else:
                candidates_at_highest_score_unmatched.append(ts_obj.text)

    final_texts_with_highest_score: List[str]
    if candidates_at_highest_score_matched:
        final_texts_with_highest_score = sorted(
            list(set(candidates_at_highest_score_matched))
        )  # Unique & sorted
    elif (
        candidates_at_highest_score_unmatched
    ):  # Only if no 'matched' items at this score
        final_texts_with_highest_score = sorted(
            list(set(candidates_at_highest_score_unmatched))
        )
    else:
        final_texts_with_highest_score = []

    if return_empty_string_if_highest_score_is_not_positive and highest_score_val <= 0:
        return "", text_scores_computed

    if not final_texts_with_highest_score:
        return "", text_scores_computed  # No candidates found or score was too low

    text_output: str
    if not return_concatenated_string_for_texts_with_same_highest_score:
        # Original TS just took [0]. Sorting makes it deterministic if multiple have same score.
        text_output = final_texts_with_highest_score[0]
    else:
        # Join sorted texts for deterministic concatenated output
        text_output = " ".join(s.strip() for s in final_texts_with_highest_score)

    return text_output.strip(), text_scores_computed
