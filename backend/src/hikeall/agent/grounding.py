"""Deterministic grounding check: every number with a unit in a model answer must come from the
round's tool results (or the code's own sentences); unsupported numbers become "?"."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# Adapted from HikeAI pipeline/grounding.py::_NUMBER_WITH_UNIT for German answers:
# decimal comma, dot as thousands separator ("1.200 Hm"), German unit words; "km/h" is no length.
_NUMBER_WITH_UNIT = re.compile(
    r"(?<![\w.,])(?P<num>\d{1,3}(?:\.\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?)"
    r"\s?(?P<unit>km|Höhenmetern?|hm|m|Stunden?|Std\.?|h|Minuten?|min|%)(?![\w/²³])",
    re.IGNORECASE,
)

# unit -> (dimension, factor to the dimension's base unit)
_UNITS = {
    "km": ("length", Decimal(1000)),
    "m": ("length", Decimal(1)),
    "hm": ("length", Decimal(1)),
    "höhenmeter": ("length", Decimal(1)),
    "höhenmetern": ("length", Decimal(1)),
    "h": ("time", Decimal(60)),
    "std": ("time", Decimal(60)),
    "std.": ("time", Decimal(60)),
    "stunde": ("time", Decimal(60)),
    "stunden": ("time", Decimal(60)),
    "min": ("time", Decimal(1)),
    "minute": ("time", Decimal(1)),
    "minuten": ("time", Decimal(1)),
    "%": ("percent", Decimal(1)),
}

HINT = "Hinweis: {n} Angabe(n) ließ(en) sich nicht belegen und wurde(n) entfernt."


@dataclass
class Evidence:
    """What the round's tool results (and the code's own sentences) say.

    numbers: texts containing numbers with units, e.g. "12.4 km" or a code-built sentence.
    names: tours, places, lodgings, POIs, source titles (kept for the prompt and the report;
    the check itself only verifies numbers).
    """

    numbers: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)

    def add(self, value: float | None, unit: str) -> None:
        if value is None or isinstance(value, bool):
            return
        text = f"{float(value):.6f}".rstrip("0").rstrip(".").replace(".", ",")
        self.numbers.append(f"{text} {unit}")

    def add_name(self, name: str | None) -> None:
        if name and name not in self.names:
            self.names.append(name)


@dataclass
class GroundingResult:
    text: str
    unsupported: list[str]


@dataclass(frozen=True)
class _Number:
    value: Decimal
    decimals: int
    dim: str
    factor: Decimal


def numbers_in_text(text: str) -> list[str]:
    return [m.group(0) for m in _NUMBER_WITH_UNIT.finditer(text)]


def _parse(match: re.Match) -> _Number:
    raw = match.group("num")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):  # German thousands separator
        raw, decimals = raw.replace(".", ""), 0
    else:
        raw = raw.replace(",", ".")
        decimals = len(raw.split(".")[1]) if "." in raw else 0
    dim, factor = _UNITS[match.group("unit").lower()]
    return _Number(Decimal(raw), decimals, dim, factor)


def _evidence_numbers(evidence: Evidence) -> list[_Number]:
    return [_parse(m) for text in evidence.numbers for m in _NUMBER_WITH_UNIT.finditer(text)]


def _round(x: Decimal, decimals: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _supported(n: _Number, known: list[_Number]) -> bool:
    for k in known:
        if k.dim != n.dim:
            continue
        base = k.value * k.factor
        candidates = [base / n.factor]
        if k.dim == "time" and n.factor == 1:  # "2 h 30 min": minutes part of an hour value
            candidates.append(base % 60)
        if k.dim == "time" and n.factor == 60 and n.decimals == 0:  # ... and its hours part
            candidates.append(Decimal(int(base // 60)))
        if any(_round(c, n.decimals) == n.value for c in candidates):
            return True
    return False


def grounding_check(answer: str, evidence: Evidence) -> GroundingResult:
    known = _evidence_numbers(evidence)
    unsupported: list[str] = []
    parts: list[str] = []
    pos = 0
    for m in _NUMBER_WITH_UNIT.finditer(answer):
        if _supported(_parse(m), known):
            continue
        unsupported.append(m.group(0))
        parts += [answer[pos : m.start("num")], "?"]
        pos = m.end("num")
    text = "".join(parts) + answer[pos:]
    if unsupported:
        text = text.rstrip() + "\n\n" + HINT.format(n=len(unsupported))
    return GroundingResult(text=text, unsupported=unsupported)
