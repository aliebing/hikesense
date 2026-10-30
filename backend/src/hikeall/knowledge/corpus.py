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
STATUSES = ("entwurf", "geprüft")
_HEADING = re.compile(r"^=+\s*(.*?)\s*=+$")

# Wikivoyage listings in the plain-text extract: "4\u200b Name, Adresse. Tel.: +49 …, E-Mail: …
# .letzte Änderung: keine Angabe48.596718.20157" (marker, contacts, edit note, lat+lon glued).
# Phone numbers and coordinates are noise for retrieval and invite unsupported numbers.
_LAT = r"(?:4[5-9]|5[0-5])\.\d+"  # Germany and its neighbours, decimal degrees
_LON = r"(?:[5-9]|1[0-5])\.\d+"
_WV_NOISE = [
    re.compile(r"letzte Änderung:\s*(?:keine Angabe|[^\W\d]*\.?\s*\d{4})"),
    re.compile(rf"(?<![\d.]){_LAT}\s*,\s*{_LON}(?!\d)"),  # "47.9, 8.1"
    re.compile(rf"(?<![\d.]){_LAT}{_LON}(?!\d)"),  # lat and lon glued together
    re.compile(r"\b(?:lat|long|lon)\s*=\s*-?[\d.]+"),
    re.compile(r"\b(?:Tel\.|Telefon|Fax|Mobil)\s*:?\s*\+?[\d\s()/-]*\d"),
    re.compile(r"\bE-Mail\s*:?\s*[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    re.compile(r"\+\d{2}\s*(?:\(0\))?[\d\s/-]*\d"),  # a bare international number
    re.compile(r"\d+\u200b"),  # listing marker "4\u200b"
    re.compile(r"\u200b"),
]


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
    source_urls: tuple[str, ...] = ()
    status: str | None = None  # own texts only


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    title: str
    url: str
    license: str
    source_urls: tuple[str, ...] = ()
    status: str | None = None


def clean_wikivoyage(text: str) -> str:
    """Wikivoyage extract without phone numbers, coordinates and listing remains (per line)."""
    lines = []
    for line in text.splitlines():
        if _HEADING.match(line.strip()):
            lines.append(line)
            continue
        for rx in _WV_NOISE:
            line = rx.sub(" ", line)
        line = re.sub(r"\(\s*\)", " ", line)  # brackets left empty
        line = re.sub(r"\s+([.,])", r"\1", line)  # "Pforzheim ." -> "Pforzheim."
        line = re.sub(r"([.,])(?:\s*[.,])+", r"\1", line)  # ". , ." -> "."
        line = re.sub(r"\s+", " ", line).strip()
        line = line.lstrip(".,").strip()
        lines.append(line)
    return "\n".join(lines)


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
                text=clean_wikivoyage(page.text) if "wikivoyage" in src.site else page.text,
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
        if (
            not isinstance(sources, list)
            or not sources
            or not all(
                isinstance(u, str) and u.startswith(("http://", "https://")) for u in sources
            )
        ):
            raise KnowledgeError(f"{path.name}: sources muss eine nicht leere Liste von URLs sein")
        status = meta.get("status")
        if status not in STATUSES:
            raise KnowledgeError(f"{path.name}: status muss 'entwurf' oder 'geprüft' sein")
        title = str(meta.get("title") or path.stem)
        if status == "entwurf":
            title += " (Entwurf)"
        docs.append(
            Article(
                site="own",
                title=title,
                url=sources[0],
                text=parts[2].strip(),
                license=WIKI_LICENSE,
                source_urls=tuple(sources),
                status=status,
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
                Chunk(
                    f"{slug}-{len(chunks)}",
                    f"{head}\n{body}",
                    doc.title,
                    doc.url,
                    doc.license,
                    doc.source_urls,
                    doc.status,
                )
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
