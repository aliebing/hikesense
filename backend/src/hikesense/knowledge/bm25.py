"""BM25 keyword index: catches exact names (Westweg, Feldberg) that embeddings miss."""

from __future__ import annotations

import re
import unicodedata

from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"\w+")
_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def fold(text: str) -> str:
    text = text.casefold().translate(_FOLD)
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(fold(text))


class BM25Index:
    def __init__(self, docs: list[tuple[str, str]]) -> None:
        if not docs:
            raise ValueError("BM25 index needs at least one document")
        self._ids = [doc_id for doc_id, _ in docs]
        self._tokens = [tokenize(text) or ["_"] for _, text in docs]
        self._bm25 = BM25Okapi(self._tokens)

    def rank(self, query: str, top_n: int = 50) -> list[str]:
        tokens = tokenize(query)
        if not tokens:
            return []
        wanted = set(tokens)
        scores = self._bm25.get_scores(tokens)
        pairs = [
            (doc_id, float(score))
            for doc_id, score, doc_tokens in zip(self._ids, scores, self._tokens, strict=True)
            if score > 0 or (score == 0 and wanted & set(doc_tokens))
        ]
        pairs.sort(key=lambda p: (-p[1], p[0]))
        return [doc_id for doc_id, _ in pairs[:top_n]]
