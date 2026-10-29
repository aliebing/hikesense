"""Knowledge corpus: article list, MediaWiki fetch, own texts with frontmatter, chunking."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

from hikeall.adapters.mediawiki import WIKI_LICENSE, MediaWikiClient
from hikeall.errors import KnowledgeError

# Sections that hold no prose worth retrieving.
SKIP_SECTIONS = {
    "literatur",
    "weblinks",
    "einzelnachweise",
    "siehe auch",
    "anmerkungen",
    "fußnoten",
}
_HEADING = re.compile(r"^=+\s*(.*?)\s*=+$")


@dataclass(frozen=True)
class Source:
    site: str
    title: str


@dataclass(frozen=True)
class Article:
    site: str
    title: str
    url: str
    text: str
    license: str


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    title: str
    url: str
    license: str


def load_sources(path: Path) -> list[Source]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [Source(site=str(r["site"]), title=str(r["title"])) for r in raw]


def fetch_articles(
    http: httpx.Client,
    sources: list[Source],
    on_missing: Callable[[Source], None] | None = None,
    backoff_s: float = 1.0,
) -> list[Article]:
    """Fetch every source; a missing article is reported via `on_missing`, never fatal."""
    client = MediaWikiClient(http, backoff_s=backoff_s)
    articles: list[Article] = []
    for src in sources:
        page = client.page_text(src.site, src.title)
        if page is None:
            if on_missing:
                on_missing(src)
            continue
        articles.append(
            Article(
                site=src.site,
                title=f"{page.title} ({src.site.split('.')[1].capitalize()})",
                url=page.url,
                text=page.text,
                license=WIKI_LICENSE,
            )
        )
    return articles


def load_own_texts(directory: Path) -> list[Article]:
    """Own texts `*.md` with frontmatter `title`, `sources: [url…]`, `status`."""
    docs: list[Article] = []
    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        if not raw.startswith("---") or len(parts) < 3:
            raise KnowledgeError(f"{path.name}: Frontmatter fehlt")
        meta = yaml.safe_load(parts[1]) or {}
        sources = meta.get("sources")
        if not sources or not isinstance(sources, list):
            raise KnowledgeError(f"{path.name}: Frontmatter braucht sources (Liste von URLs)")
        title = str(meta.get("title") or path.stem)
        if meta.get("status", "entwurf") != "geprüft":
            title += " (Entwurf)"
        docs.append(
            Article(
                site="own",
                title=title,
                url=str(sources[0]),
                text=parts[2].strip(),
                license=WIKI_LICENSE,
            )
        )
    return docs


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "doc"


def _sections(text: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        m = _HEADING.match(line.strip())
        if m:
            sections.append((m.group(1), []))
        elif line.strip():
            sections[-1][1].append(line.strip())
    return [(h, p) for h, p in sections if p and h.casefold() not in SKIP_SECTIONS]


def _split_long(paragraph: str, limit: int) -> list[str]:
    pieces: list[str] = []
    while len(paragraph) > limit:
        cut = paragraph.rfind(" ", 0, limit)
        cut = cut if cut > 0 else limit
        pieces.append(paragraph[:cut].strip())
        paragraph = paragraph[cut:].strip()
    return pieces + [paragraph] if paragraph else pieces


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    tail = text[-overlap:]
    return tail.split(" ", 1)[1] if " " in tail and len(text) > overlap else tail


def chunk(doc: Article, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    """Merge paragraphs into chunks <= max_chars; each chunk starts with 'Titel – Überschrift'."""
    chunks: list[Chunk] = []
    slug = _slug(doc.title)
    for heading, paragraphs in _sections(doc.text):
        head = f"{doc.title} – {heading}" if heading else doc.title
        room = max_chars - len(head) - 1  # body incl. carried overlap
        pieces = [p for para in paragraphs for p in _split_long(para, room - overlap - 1)]
        carry, cur = "", ""

        def emit(carry: str, cur: str, head: str = head) -> None:
            body = f"{carry}\n{cur}" if carry else cur
            chunks.append(
                Chunk(f"{slug}-{len(chunks)}", f"{head}\n{body}", doc.title, doc.url, doc.license)
            )

        for piece in pieces:
            cand = f"{cur}\n{piece}" if cur else piece
            if len(carry) + 1 + len(cand) <= room:
                cur = cand
                continue
            emit(carry, cur)
            carry, cur = _tail(cur, overlap), piece
        if cur:
            emit(carry, cur)
    return chunks
