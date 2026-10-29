"""Hybrid search: ChromaDB (embedded, persisted) vectors + BM25, fused with RRF (k=60)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from hikeall.agent.tools import KnowledgeHit
from hikeall.errors import KnowledgeError
from hikeall.knowledge.bm25 import BM25Index
from hikeall.knowledge.corpus import Chunk
from hikeall.knowledge.fusion import rrf

COLLECTION = "knowledge"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RRF_K = 60
CANDIDATES = 20


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedder:
    """Local ONNX embeddings (no API cost); the model is downloaded on first use."""

    def __init__(self, model: str = EMBEDDING_MODEL) -> None:
        self._model_name = model
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
        return [[float(x) for x in v] for v in self._model.embed(texts)]


def _client(path: Path):
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


class KnowledgeIndex:
    def __init__(self, collection, embedder: Embedder) -> None:
        self._collection = collection
        self._embedder = embedder
        stored = collection.get(include=["documents", "metadatas"])
        self._ids: list[str] = stored["ids"]
        self._docs: dict[str, tuple[str, dict]] = {
            i: (d, m) for i, d, m in zip(stored["ids"], stored["documents"], stored["metadatas"])
        }
        self._bm25 = BM25Index(list(zip(self._ids, stored["documents"]))) if self._ids else None

    @classmethod
    def build(cls, chunks: list[Chunk], path: Path, embedder: Embedder) -> KnowledgeIndex:
        if not chunks:
            raise KnowledgeError("Keine Chunks zum Indexieren")
        path = Path(path)
        if path.exists():
            shutil.rmtree(path)
        collection = _client(path).get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"}
        )
        for i in range(0, len(chunks), 64):
            batch = chunks[i : i + 64]
            collection.add(
                ids=[c.id for c in batch],
                documents=[c.text for c in batch],
                embeddings=embedder.embed([c.text for c in batch]),
                metadatas=[{"title": c.title, "url": c.url, "license": c.license} for c in batch],
            )
        return cls(collection, embedder)

    @classmethod
    def open(cls, path: Path, embedder: Embedder) -> KnowledgeIndex:
        path = Path(path)
        if not path.exists():
            raise KnowledgeError("Wissensindex fehlt")
        try:
            collection = _client(path).get_collection(COLLECTION)
        except Exception as e:  # chromadb raises its own NotFound/ValueError types
            raise KnowledgeError("Wissensindex fehlt") from e
        if collection.count() == 0:
            raise KnowledgeError("Wissensindex ist leer")
        return cls(collection, embedder)

    def search(self, query: str, k: int = 5) -> list[KnowledgeHit]:
        n = min(CANDIDATES, len(self._ids))
        res = self._collection.query(
            query_embeddings=self._embedder.embed([query]), n_results=n, include=[]
        )
        vector_ids = res["ids"][0]
        keyword_ids = self._bm25.rank(query, top_n=CANDIDATES) if self._bm25 else []
        scores = rrf([vector_ids, keyword_ids], k=RRF_K)
        best = sorted(scores, key=lambda i: (-scores[i], i))[:k]
        hits = []
        for doc_id in best:
            text, meta = self._docs[doc_id]
            hits.append(
                KnowledgeHit(
                    text=text,
                    source_id=doc_id,
                    title=meta["title"],
                    url=meta["url"],
                    license=meta["license"],
                    score=scores[doc_id],
                )
            )
        return hits


def try_open(path: Path, embedder: Embedder | None = None) -> KnowledgeIndex | None:
    """Open the persisted index, or None if it was never built (`make knowledge`)."""
    try:
        return KnowledgeIndex.open(path, embedder or FastEmbedder())
    except KnowledgeError:
        return None
