"""Reciprocal Rank Fusion (adapted from HikeAI)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence


def rrf(rank_lists: Sequence[Sequence[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rank_lists:
        for position, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += 1.0 / (k + position)
    return dict(scores)
