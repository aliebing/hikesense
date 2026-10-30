import re
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from hikeall.adapters.http import make_http_client
from hikeall.agent.tools import DbTools
from hikeall.agent.tools import KnowledgeHit as ToolsHit
from hikeall.errors import KnowledgeError
from hikeall.knowledge.bm25 import BM25Index, tokenize
from hikeall.knowledge.corpus import (
    Article,
    Chunk,
    Source,
    chunk,
    clean_wikivoyage,
    fetch_articles,
    load_own_texts,
)
from hikeall.knowledge.fusion import rrf
from hikeall.knowledge.models import KnowledgeHit
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


def test_own_text_hits_keep_all_sources_and_status(tmp_path):
    (tmp_path / "a.md").write_text(
        "---\ntitle: Zeichen\nsources:\n  - https://a.example/1\n  - https://b.example/2\n"
        "status: entwurf\n---\nRote Raute Westweg.",
        encoding="utf-8",
    )
    chunks = [c for d in load_own_texts(tmp_path) for c in chunk(d)]
    idx = KnowledgeIndex.build([*chunks, *make_chunks()], tmp_path / "chroma", FakeEmbedder())
    own = next(h for h in idx.search("Raute Westweg", k=5) if h.title.startswith("Zeichen"))
    assert own.source_urls == ["https://a.example/1", "https://b.example/2"]
    assert own.status == "entwurf"
    art = next(h for h in idx.search("Feldberg", k=5) if h.title == "Feldberg")
    assert art.source_urls == [art.url] and art.status is None


def test_knowledge_hit_reexported_from_agent_tools():
    assert ToolsHit is KnowledgeHit


@pytest.mark.parametrize(
    "front",
    [
        "title: A\nstatus: geprueft\nsources:\n  - https://x.example",
        "title: A\nstatus: entwurf\nsources:\n  - nicht-eine-url",
        "title: A\nstatus: entwurf\nsources: https://x.example",
        "title: A\nsources:\n  - https://x.example",
    ],
)
def test_frontmatter_validation(tmp_path, front):
    (tmp_path / "a.md").write_text(f"---\n{front}\n---\nText", encoding="utf-8")
    with pytest.raises(KnowledgeError):
        load_own_texts(tmp_path)


def test_try_open_returns_none_on_corrupt_dir(tmp_path):
    (tmp_path / "chroma.sqlite3").write_text("kein sqlite", encoding="utf-8")
    assert try_open(tmp_path, FakeEmbedder()) is None


def test_bm25_folds_umlauts():
    assert tokenize("Hütte Straße Müller") == tokenize("Huette Strasse Mueller")
    idx = BM25Index([("a", "Die Hütte am Berg"), ("b", "Nichts hier")])
    assert idx.rank("huette") == ["a"]


def test_chunk_overlap_repeats_tail_of_previous_chunk():
    para = " ".join(f"wort{i}" for i in range(400))
    chunks = chunk(article(para), max_chars=500, overlap=100)
    assert len(chunks) >= 3
    for prev, nxt in pairwise(chunks):
        last_words = prev.text.split()[-3:]
        assert " ".join(last_words) in nxt.text


def test_real_own_texts_load():
    docs = load_own_texts(Path(__file__).resolve().parents[2] / "data" / "knowledge")
    assert len(docs) == 4
    assert all(d.status == "entwurf" and d.source_urls for d in docs)


# --- Wikivoyage noise (plan 3, task 13) ------------------------------------------------------

# Real lines of de.wikivoyage.org "Westweg" and "Schwarzwald" (plain-text extract, CC BY-SA 4.0).
WV_EXCERPT = Path(__file__).parent / "fixtures" / "wikivoyage_excerpt.txt"
_GLUED = re.compile(r"4[789]\.\d+[5-9]\.\d+")


def test_wikivoyage_noise_removed_from_real_excerpt():
    raw = WV_EXCERPT.read_text(encoding="utf-8")
    assert "Tel." in raw and "+49" in raw and _GLUED.search(raw)  # the fixture is noisy
    text = clean_wikivoyage(raw)
    for noise in ("Tel.", "Fax", "+49", "+41", "@", "letzte Änderung", "\u200b"):
        assert noise not in text, noise
    assert not _GLUED.search(text)
    assert not re.search(r"\d{4,} ?\d{3,}", text.replace("75181 Pforzheim", ""))  # no numbers
    # prose, names, addresses and opening hours stay
    assert "Gasthaus Kupferhammer, Am Kupferhammer 1, 75181 Pforzheim." in text
    assert "Vom Ausgangspunkt in Unterstmatt führt der Weg zunächst links" in text
    assert "zum Schloss Neuenbürg." in text
    assert "Geöffnet: MO geschlossen." in text
    assert "Nordschwarzwald. hochmoor- und fichtenwaldreiche Gegend" in text
    assert "== Regionen ==" in text  # headings untouched for chunking
    assert not re.search(r"\s[.,]|[.,]\s*[.,]", text)  # no punctuation left over


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("Start am Bahnhof (47.9, 8.1) bergauf.", "Start am Bahnhof bergauf."),
        ("Hütte lat=47.912 long=8.123 mit Blick.", "Hütte mit Blick."),
        (
            "Flughafen (IATA: FRA) 50.0333055555568.5704555555556 nördlich.",
            "Flughafen (IATA: FRA) nördlich.",
        ),
        ("Ruf an: +49 7652 382 oder komm vorbei.", "Ruf an: oder komm vorbei."),
        (
            "Die Mobilität ist gut, 4,5 km und 1.200 Hm.",
            "Die Mobilität ist gut, 4,5 km und 1.200 Hm.",
        ),
    ],
)
def test_wikivoyage_noise_patterns(raw, clean):
    assert clean_wikivoyage(raw) == clean


def test_only_wikivoyage_articles_are_cleaned(respx_mock):
    noisy = "Hütte am Weg. Tel.: +49 7652 382 .letzte Änderung: keine Angabe47.92668.1248"
    for site in ("de.wikipedia.org", "de.wikivoyage.org"):
        respx_mock.get(f"https://{site}/w/api.php").mock(
            return_value=httpx.Response(200, json=wiki_page("Westweg", noisy))
        )
    with make_http_client(5) as http:
        wp, wv = fetch_articles(
            http,
            [Source("de.wikipedia.org", "Westweg"), Source("de.wikivoyage.org", "Westweg")],
            backoff_s=0,
        )
    assert wp.text == noisy
    assert wv.text == "Hütte am Weg."
