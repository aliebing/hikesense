"""Real code for the code slides of the technical video: read from the repository at recording time (by function
name or by first/last line), so the video always shows the code as it is — nothing is typed off by hand.
Adapted from CineSense (scripts/video/code_snippets.py)."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_for_filename

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Snippet:
    file: str  # repo-relative path
    function: str | None = None  # "name", "Class.name" or "outer_function.inner"; the first match
    start: str | None = None  # or: the first line containing this text …
    end: str | None = None  # … up to and including the next line containing this text
    mark: list[str] = field(default_factory=list)  # lines containing any of these are highlighted


def _function_lines(source: str, name: str) -> tuple[int, int]:
    owner, _, fn = name.rpartition(".")
    tree = ast.parse(source)
    defs = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    scopes = [n for n in ast.walk(tree) if isinstance(n, defs) and n.name == owner] if owner else [tree]
    for scope in scopes:
        for n in ast.walk(scope):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == fn:
                first = min([n.lineno] + [d.lineno for d in n.decorator_list])
                return first, n.end_lineno
    raise LookupError(f"{name} not found")


def _anchor_lines(lines: list[str], start: str, end: str) -> tuple[int, int]:
    a = next(i for i, line in enumerate(lines, 1) if start in line)
    b = next(i for i, line in enumerate(lines, 1) if i >= a and end in line)
    return a, b


def lines_of(s: Snippet) -> tuple[int, int, list[str]]:
    """First and last line number (1-based) and the lines themselves, dedented to the snippet's own indent."""
    source = (ROOT / s.file).read_text(encoding="utf-8")
    lines = source.splitlines()
    a, b = _function_lines(source, s.function) if s.function else _anchor_lines(lines, s.start, s.end)
    chunk = lines[a - 1 : b]
    indent = min(len(x) - len(x.lstrip()) for x in chunk if x.strip())
    return a, b, [x[indent:] for x in chunk]


def render(s: Snippet) -> str:
    """One code panel: file name and line range as a header, highlighted code with real line numbers."""
    a, b, chunk = lines_of(s)
    marked = [i for i, line in enumerate(chunk, 1) if any(m in line for m in s.mark)]
    fmt = HtmlFormatter(nowrap=False, linenos="inline", linenostart=a, hl_lines=marked, cssclass="src")
    code = highlight("\n".join(chunk) + "\n", get_lexer_for_filename(s.file), fmt)
    return f'<div class="codehead">{escape(s.file)} <span>· lines {a}–{b}</span></div>{code}'


def render_slides(slides: dict[str, list[Snippet]]) -> dict[str, list[str]]:
    return {key: [render(s) for s in snippets] for key, snippets in slides.items()}
