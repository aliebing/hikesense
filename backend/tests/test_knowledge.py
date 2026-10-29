import httpx
import pytest

from hikeall.adapters.http import make_http_client
from hikeall.agent.tools import DbTools
from hikeall.errors import KnowledgeError
from hikeall.knowledge.corpus import (
    Article,
    Chunk,
    Source,
    chunk,
    fetch_articles,
    load_own_texts,
)
from hikeall.knowledge.fusion import rrf
from hikeall.knowledge.search import KnowledgeIndex, try_open

WORDS = ["westweg", "raute", "wasser", "hütte", "feldberg"]


class FakeEmbedder:
    """Fixed vectors: one dimension per keyword (substring count)."""

    def embed(self, texts):
        return [[float(t.casefold().count(w)) + 0.01 for w in WORDS] for t in texts]


def article(text, title="Westweg"):
    return Article(
        site="de.wikipedia.org",
        title=title,
        url=f"https://de.wikipedia.org/w/index.php?title={title}&oldid=7",
        text=text,
        license="CC BY-SA 4.0",
    )


def test_chunk_keeps_heading_and_limit():
    para = "Satz eins ist hier. " * 20  # 400 chars
    text = f"Intro.\n\n== Markierung ==\n{para}\n{para}\n{para}\n{para}\n\n== Anfahrt ==\nBus."
    chunks = chunk(article(text), max_chars=1000, overlap=100)
    assert len(chunks) >= 3
    assert all(len(c.text) <= 1000 for c in chunks)
    marking = [c for c in chunks if "Satz eins" in c.text]
    assert all(c.text.startswith("Westweg – Markierung") for c in marking)
    assert any(c.text.startswith("Westweg – Anfahrt") and "Bus." in c.text for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)
    assert chunks[0].url.endswith("oldid=7") and chunks[0].license == "CC BY-SA 4.0"


def test_chunk_drops_reference_sections():
    text = "Inhalt hier.\n\n== Weblinks ==\nhttp://example.org"
    assert all("example.org" not in c.text for c in chunk(article(text)))


def test_rrf_prefers_doc_in_both_lists():
    scores = rrf([["a", "b", "c"], ["d", "b", "e"]], k=60)
    best = sorted(scores, key=lambda i: (-scores[i], i))
    assert best[:2] == ["b", "a"]
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 62)


def make_chunks():
    return [
        Chunk(
            "w-0",
            "Westweg – Zeichen\nDie rote Raute auf weißem Grund markiert den Westweg.",
            "Westweg",
            "https://de.wikipedia.org/w/index.php?title=Westweg&oldid=7",
            "CC BY-SA 4.0",
        ),
        Chunk(
            "f-0",
            "Feldberg\nDer Feldberg ist der höchste Berg.",
            "Feldberg",
            "https://de.wikipedia.org/w/index.php?title=Feldberg&oldid=9",
            "CC BY-SA 4.0",
        ),
        Chunk(
            "h-0",
            "Hütten\nEine Hütte bietet Wasser und Essen.",
            "Hütten",
            "https://example.org/h",
            "CC BY-SA 4.0",
        ),
    ]


def test_search_returns_source_url_and_license(tmp_path):
    idx = KnowledgeIndex.build(make_chunks(), tmp_path / "chroma", FakeEmbedder())
    hits = idx.search("rote Raute Westweg", k=2)
    assert hits[0].title == "Westweg"
    assert hits[0].url.endswith("oldid=7")
    assert hits[0].license == "CC BY-SA 4.0"
    assert hits[0].source_id == "w-0" and hits[0].score > 0
    assert len(hits) == 2
    reopened = KnowledgeIndex.open(tmp_path / "chroma", FakeEmbedder())
    assert reopened.search("Feldberg", k=1)[0].title == "Feldberg"


def test_missing_index_is_reported_not_raised(tmp_path):
    assert try_open(tmp_path / "nothing", FakeEmbedder()) is None
    hits = DbTools(lambda: None, try_open(tmp_path / "nothing", FakeEmbedder())).search_knowledge(
        "x"
    )
    assert hits[0].text == "Wissensindex fehlt – `make knowledge` ausführen"


def wiki_page(title, extract, revid=5):
    return {
        "query": {
            "pages": [
                {
                    "title": title,
                    "extract": extract,
                    "revisions": [{"revid": revid}],
                }
            ]
        }
    }


def test_missing_article_is_reported_not_fatal(respx_mock):
    def handler(request: httpx.Request) -> httpx.Response:
        title = request.url.params["titles"]
        if title == "Gibtsnicht":
            return httpx.Response(
                200, json={"query": {"pages": [{"title": title, "missing": True}]}}
            )
        return httpx.Response(200, json=wiki_page(title, "Text über den Westweg."))

    respx_mock.get("https://de.wikipedia.org/w/api.php").mock(side_effect=handler)
    missing = []
    with make_http_client(5) as http:
        arts = fetch_articles(
            http,
            [Source("de.wikipedia.org", "Westweg"), Source("de.wikipedia.org", "Gibtsnicht")],
            on_missing=missing.append,
            backoff_s=0,
        )
    assert [a.title for a in arts] == ["Westweg (Wikipedia)"]
    assert arts[0].url == "https://de.wikipedia.org/w/index.php?title=Westweg&oldid=5"
    assert arts[0].license == "CC BY-SA 4.0"
    assert [s.title for s in missing] == ["Gibtsnicht"]


def test_frontmatter_requires_sources(tmp_path):
    (tmp_path / "a.md").write_text("---\ntitle: A\nstatus: entwurf\n---\nText", encoding="utf-8")
    with pytest.raises(KnowledgeError, match="sources"):
        load_own_texts(tmp_path)


def test_own_text_loaded_with_draft_marker(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\ntitle: Zeichen\nsources:\n  - https://de.wikipedia.org/wiki/Westweg\n"
        "status: entwurf\n---\nRaute.",
        encoding="utf-8",
    )
    (doc,) = load_own_texts(tmp_path)
    assert doc.title == "Zeichen (Entwurf)"
    assert doc.url == "https://de.wikipedia.org/wiki/Westweg" and doc.text == "Raute."
