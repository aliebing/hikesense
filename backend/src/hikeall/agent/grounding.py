"""Deterministic grounding check: every number with a unit in a model answer must come from the
round's tool results (or the code's own sentences); unsupported numbers become "?"."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# Adapted from HikeAI pipeline/grounding.py::_NUMBER_WITH_UNIT for German answers:
# decimal comma, dot as thousands separator ("1.200 Hm"), German unit words; "km/h" is no length.
_NUM = r"\d{1,3}(?:\.\d{3})+(?![.,]?\d)|\d+(?:[.,]\d+)?"
_UNIT_RE = r"Kilometern?|km|Höhenmetern?|hm|Metern?|m|Stunden?|Std\.?|h|Minuten?|min|Prozent|%"
_HOURS = r"(?:Stunden?|Std\.?|h)"
_MINUTES = r"(?:Minuten?|min)"
_START = r"(?<![\w.,:])"
_END = r"(?![\w/²³])"
_NUMBER_WITH_UNIT = re.compile(
    # "2 h 54 min" / "2 Std. 54 Minuten": one duration
    rf"{_START}(?P<ch>\d+)\s?{_HOURS}\s?(?:und\s)?(?P<cm>\d{{1,2}})\s?{_MINUTES}{_END}"
    # "2:54 h": one duration
    rf"|{_START}(?P<kh>\d+):(?P<km>\d{{2}})\s?{_HOURS}{_END}"
    # "10 bis 15 km", "10–15 km", "zwischen 10 und 15 km": both numbers carry the unit
    rf"|{_START}(?:(?P<lo>{_NUM})\s?(?:–|—|-|bis\s|und\s)\s?)?"
    rf"(?P<num>{_NUM})\s?(?P<unit>{_UNIT_RE}){_END}",
    re.IGNORECASE,
)

# unit -> (dimension, factor to the dimension's base unit). Höhenmeter are their own dimension:
# an ascent never supports a length and vice versa.
_LENGTH = {"km": 1000, "kilometer": 1000, "kilometern": 1000, "m": 1, "meter": 1, "metern": 1}
_ASCENT = {"hm": 1, "höhenmeter": 1, "höhenmetern": 1}
_TIME = {"h": 60, "std": 60, "std.": 60, "stunde": 60, "stunden": 60}
_TIME |= {"min": 1, "minute": 1, "minuten": 1}
_UNITS = {
    **{u: ("length", Decimal(f)) for u, f in _LENGTH.items()},
    **{u: ("ascent", Decimal(f)) for u, f in _ASCENT.items()},
    **{u: ("time", Decimal(f)) for u, f in _TIME.items()},
    "%": ("percent", Decimal(1)),
    "prozent": ("percent", Decimal(1)),
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


@dataclass(frozen=True)
class _Found:
    """One number to check: its span(s) in the text (replaced by "?") and how it is reported."""

    number: _Number
    spans: tuple[tuple[int, int], ...]
    shown: str


def _value(raw: str) -> tuple[Decimal, int]:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):  # German thousands separator
        return Decimal(raw.replace(".", "")), 0
    raw = raw.replace(",", ".")
    return Decimal(raw), len(raw.split(".")[1]) if "." in raw else 0


def _found(text: str) -> list[_Found]:
    out: list[_Found] = []
    for m in _NUMBER_WITH_UNIT.finditer(text):
        if m.group("ch") is not None or m.group("kh") is not None:  # compound duration
            h, mins = ("ch", "cm") if m.group("ch") is not None else ("kh", "km")
            total = Decimal(m.group(h)) * 60 + Decimal(m.group(mins))
            number = _Number(total, 0, "time", Decimal(1))
            out.append(_Found(number, (m.span(h), m.span(mins)), m.group(0)))
            continue
        unit = m.group("unit")
        dim, factor = _UNITS[unit.lower()]
        if m.group("lo") is not None:  # range: the first number has the same unit
            value, decimals = _value(m.group("lo"))
            number = _Number(value, decimals, dim, factor)
            out.append(_Found(number, (m.span("lo"),), f"{m.group('lo')} {unit}"))
        value, decimals = _value(m.group("num"))
        number = _Number(value, decimals, dim, factor)
        out.append(_Found(number, (m.span("num"),), text[m.start("num") : m.end()]))
    return out


def numbers_in_text(text: str) -> list[str]:
    return [f.shown for f in _found(text)]


def _evidence_numbers(evidence: Evidence) -> list[_Number]:
    return [f.number for text in evidence.numbers for f in _found(text)]


def _round(x: Decimal, decimals: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _supported(n: _Number, known: list[_Number]) -> bool:
    """Equal after converting the evidence to the answer's unit and rounding it to the answer's
    precision. Durations count only as a whole: "2 h" or "54 min" alone is not 2,9 h."""
    return any(
        k.dim == n.dim and _round(k.value * k.factor / n.factor, n.decimals) == n.value
        for k in known
    )


def grounding_check(answer: str, evidence: Evidence) -> GroundingResult:
    known = _evidence_numbers(evidence)
    unsupported: list[str] = []
    spans: list[tuple[int, int]] = []
    for f in _found(answer):
        if not _supported(f.number, known):
            unsupported.append(f.shown)
            spans += f.spans
    parts: list[str] = []
    pos = 0
    for start, end in sorted(spans):
        parts += [answer[pos:start], "?"]
        pos = end
    text = "".join(parts) + answer[pos:]
    if unsupported:
        text = text.rstrip() + "\n\n" + HINT.format(n=len(unsupported))
    return GroundingResult(text=text, unsupported=unsupported)
