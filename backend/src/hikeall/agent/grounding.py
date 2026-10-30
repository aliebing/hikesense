"""Deterministic grounding check: every number with a unit in a model answer must come from the
round's tool results (or the code's own sentences); unsupported numbers become "?". Tour names
from the database that the round's evidence does not mention are counted (never removed)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

# Adapted from HikeAI pipeline/grounding.py::_NUMBER_WITH_UNIT for German answers:
# decimal comma, dot as thousands separator ("1.200 Hm"), German unit words; "km/h" is no length.
# German number words (1–12, halves) count like digits: "zwei Stunden" is a claim as well.
_WORDS = {
    "eins": 1, "ein": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1, "zwei": 2, "drei": 3,
    "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11,
    "zwölf": 12,
}  # fmt: skip
_HALVES = {"anderthalb": "1.5", "eineinhalb": "1.5", "halbe": "0.5", "eine halbe": "0.5"}
_NUM_WORD = r"eine\shalbe|halbe|anderthalb|eineinhalb|eins|eine[nmr]?|ein|zwei|drei|vier|fünf"
_NUM_WORD += r"|sechs|sieben|acht|neun|zehn|elf|zwölf"
# a minus sign ("-" or U+2212) directly before the digits belongs to the number: -3 °C is not 3 °C
_NUM = rf"[-−]?(?:\d{{1,3}}(?:\.\d{{3}})+(?![.,]?\d)|\d+(?:[.,]\d+)?)|(?:{_NUM_WORD})(?!\w)"
_UNIT_RE = r"Kilometern?|km|Höhenmetern?|hm|Millimetern?|mm|Metern?|m|Stunden?|Std\.?|h|Minuten?|min"
_UNIT_RE += r"|Prozent|%|°\s?C|°|Grad|Uhr"
_HOURS = r"(?:Stunden?|Std\.?|h)"
_MINUTES = r"(?:Minuten?|min)"
# no start inside a word or a number ("12.5", "1.200"); an abbreviation dot ("ca.18 km") is fine
_START = r"(?<![\w,:])(?<!\d\.)"
_SEP = r"[\s-]?"  # "15 km", "15km", "15-km-Runde"
_END = r"(?![\w/²³])"
_NUMBER_WITH_UNIT = re.compile(
    # "13:30 Uhr" / "13.30 Uhr": one clock time
    rf"{_START}(?P<uh>\d{{1,2}})[:.](?P<um>\d{{2}})\s?Uhr{_END}"
    # "2 h 54 min" / "2 Std. 54 Minuten": one duration
    rf"|{_START}(?P<ch>\d+)\s?{_HOURS}\s?(?:und\s)?(?P<cm>\d{{1,2}})\s?{_MINUTES}{_END}"
    # "2:54 h": one duration
    rf"|{_START}(?P<kh>\d+):(?P<km>\d{{2}})\s?{_HOURS}{_END}"
    # "10 bis 15 km", "10–15 km", "zwischen 10 und 15 km": both numbers carry the unit
    rf"|{_START}(?:(?P<lo>{_NUM})\s?(?:–|—|-|bis\s|und\s)\s?)?"
    rf"(?P<num>{_NUM}){_SEP}(?P<unit>{_UNIT_RE}){_END}",
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
    **{u: ("precip", Decimal(1)) for u in ("mm", "millimeter", "millimetern")},
    **{u: ("temp", Decimal(1)) for u in ("°c", "° c", "°", "grad")},
    "uhr": ("clock", Decimal(60)),  # minutes after midnight
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
    unsupported: list[str]  # numbers, replaced by "?"
    unsupported_names: list[str] = field(default_factory=list)  # tour names, counted only


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
    if raw[:1] in ("-", "−"):
        value, decimals = _value(raw[1:])
        return -value, decimals
    word = re.sub(r"\s+", " ", raw.lower())
    if word in _HALVES:
        return Decimal(_HALVES[word]), 1
    if word in _WORDS:
        return Decimal(_WORDS[word]), 0
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):  # German thousands separator
        return Decimal(raw.replace(".", "")), 0
    raw = raw.replace(",", ".")
    return Decimal(raw), len(raw.split(".")[1]) if "." in raw else 0


def _found(text: str) -> list[_Found]:
    out: list[_Found] = []
    for m in _NUMBER_WITH_UNIT.finditer(text):
        if m.group("uh") is not None:  # clock time, in minutes after midnight
            total = Decimal(m.group("uh")) * 60 + Decimal(m.group("um"))
            number = _Number(total, 0, "clock", Decimal(1))
            out.append(_Found(number, (m.span("uh"), m.span("um")), m.group(0)))
            continue
        if m.group("ch") is not None or m.group("kh") is not None:  # compound duration
            h, mins = ("ch", "cm") if m.group("ch") is not None else ("kh", "km")
            total = Decimal(m.group(h)) * 60 + Decimal(m.group(mins))
            number = _Number(total, 0, "time", Decimal(1))
            out.append(_Found(number, (m.span(h), m.span(mins)), m.group(0)))
            continue
        unit = m.group("unit")
        dim, factor = _UNITS[re.sub(r"\s+", " ", unit.lower())]
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


def has_number(evidence: Evidence, value: float, unit: str) -> bool:
    """Exactly this value (after unit conversion, no rounding) is in the evidence."""
    probe = _found(f"{float(value):.6f}".rstrip("0").rstrip(".").replace(".", ",") + f" {unit}")
    if len(probe) != 1:
        return False
    n = probe[0].number
    return any(
        k.dim == n.dim and k.value * k.factor == n.value * n.factor
        for k in _evidence_numbers(evidence)
    )


def _unsupported_names(answer: str, evidence: Evidence, tour_names: list[str]) -> list[str]:
    """Known tour names in the answer that no evidence text or name mentions (R21)."""
    said = " \n".join(evidence.names + evidence.numbers).casefold()
    taken: list[tuple[int, int]] = []
    out: list[str] = []
    for name in sorted({n for n in tour_names if n and n.strip()}, key=lambda n: (-len(n), n)):
        for m in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", answer):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append(m.span())
            if name.casefold() not in said and name not in out:
                out.append(name)
    return out


def grounding_check(
    answer: str, evidence: Evidence, tour_names: list[str] | tuple[str, ...] = ()
) -> GroundingResult:
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
    names = _unsupported_names(answer, evidence, list(tour_names))
    return GroundingResult(text=text, unsupported=unsupported, unsupported_names=names)
