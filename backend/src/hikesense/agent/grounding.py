"""Deterministic grounding check: every number with a unit in a model answer must come from the
round's tool results (or the code's own sentences); unsupported numbers become "?". Tour names
from the database that the round's evidence does not mention are counted (never removed)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from hikesense.numfmt import Lang

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
_UNIT_RE = (
    r"Kilometern?|km|Höhenmetern?|hm|Millimetern?|mm|Metern?|m|Stunden?|Std\.?|h|Minuten?|min"
)
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


# English answers (lang="en"): decimal point, thousands comma ("1,200 m"), English unit and number
# words, "to"/"and" ranges, bare clock times ("09:30", "9:30 am").
_WORDS_EN = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
}  # fmt: skip
_HALVES_EN = {"half": "0.5", "half an": "0.5", "half a": "0.5"}
_UNITS_WORD_EN = r"one|two|three|four|five|six|seven|eight|nine"
_TENS_WORD_EN = r"twenty|thirty|forty|fifty|sixty"
# longest first; "twenty-five" / "twenty five" compounds
_WORD_ALT_EN = rf"(?:{_TENS_WORD_EN})(?:[-\s](?:{_UNITS_WORD_EN}))?"
_WORD_ALT_EN += r"|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
_WORD_ALT_EN += rf"|ten|eleven|twelve|{_UNITS_WORD_EN}"
_NUM_WORD_EN = rf"half\san?|half|{_WORD_ALT_EN}|an?"  # "a km", "an hour": one
# "2 and a half", "two and a half"; "1,5" (German decimal comma in an English answer) is read as
# 1.5 so it is checked, not skipped
_NUM_EN = (
    rf"(?:\d+|{_WORD_ALT_EN})\s+and\s+a\s+half(?!\w)"
    r"|[-−]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])|\d+,\d{1,2}(?!\d)|\d+(?:\.\d+)?)"
    rf"|(?:{_NUM_WORD_EN})(?!\w)"
)
_UNIT_EN = r"kilometres?|kilometers?|km|millimetres?|millimeters?|mm|metres?|meters?|m|hm"
_UNIT_EN += r"|hours?|hrs?|h|minutes?|mins?|min|per\s?cent|percent|%|°\s?C|°|degrees?"
_UNIT_EN += r"|miles?|mi|feet|foot|ft|yards?|yd"  # imperial: no evidence has them, never supported
_HOURS_EN = r"(?:hours?|hrs?|h)"
_MINUTES_EN = r"(?:minutes?|mins?|min)"
_NUMBER_WITH_UNIT_EN = re.compile(
    # "2 h 54 min" / "2 hours and 54 minutes": one duration
    rf"{_START}(?P<ch>\d+)\s?{_HOURS_EN}\s?(?:and\s)?(?P<cm>\d{{1,2}})\s?{_MINUTES_EN}{_END}"
    # "2:54 h": one duration
    rf"|{_START}(?P<kh>\d+):(?P<km>\d{{2}})\s?{_HOURS_EN}{_END}"
    # "09:30", "9:30 am", "4 pm": one clock time (not a pace: "5:30 min/km")
    rf"|{_START}(?P<uh>\d{{1,2}})(?::(?P<um>\d{{2}}))?(?(um)|(?=\s?[ap]\.?m\.?(?!\w)))"
    rf"(?:\s?(?P<ap>[ap]\.?m\.?)(?!\w))?(?![\w:/]|\s?(?:h\b|min|hr|hour|/))"
    # "9 o'clock", "nine o'clock"
    rf"|{_START}(?P<oh>\d{{1,2}}|{_WORD_ALT_EN})\s?o'?clock\b"
    # "10 to 15 km", "10–15 km", "between 10 and 15 km": both numbers carry the unit
    rf"|{_START}(?:(?P<lo>{_NUM_EN})\s?(?:–|—|(?<!ty)-|to\s|and\s)\s?)?"
    rf"(?P<num>{_NUM_EN}){_SEP}(?P<unit>{_UNIT_EN}){_END}",
    re.IGNORECASE,
)
# "ascent 540 m", "ascent of about 540 m" / "540 m of ascent", "540 m ascent": metres of climb
_ASCENT_BEFORE = re.compile(
    r"(?:ascent|descent|climb\w*|elevation(?:\s+gain)?|uphill|downhill)[^\d.!?;]{0,25}$",
    re.IGNORECASE,
)
_LENGTH_AFTER = re.compile(r"\s?(?:long|away|off|from|(?:of\s+)?distance)\b", re.IGNORECASE)
_ASCENT_AFTER = re.compile(
    r"\s?(?:of\s+)?(?:total\s+)?(?:ascent|descent|climb\w*|elevation|uphill|downhill)\b",
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
# English: a bare "m" is metres of length OR of climb (dimension "metre", compatible with both
# unless the words around it say ascent); the German evidence unit "Hm" stays ascent
_UNITS_EN = {
    **{u: ("length", Decimal(1000)) for u in ("km", "kilometre", "kilometres", "kilometer")},
    "kilometers": ("length", Decimal(1000)),
    **{u: ("metre", Decimal(1)) for u in ("m", "metre", "metres", "meter", "meters")},
    "hm": ("ascent", Decimal(1)),
    **{u: ("imperial", Decimal(1)) for u in ("mi", "mile", "miles", "ft", "feet", "foot")},
    **{u: ("imperial", Decimal(1)) for u in ("yard", "yards", "yd")},
    **{u: ("time", Decimal(60)) for u in ("h", "hr", "hrs", "hour", "hours")},
    **{u: ("time", Decimal(1)) for u in ("min", "mins", "minute", "minutes")},
    **{u: ("percent", Decimal(1)) for u in ("%", "percent", "per cent", "percentage")},
    **{u: ("precip", Decimal(1)) for u in ("mm", "millimetre", "millimetres", "millimeter")},
    "millimeters": ("precip", Decimal(1)),
    **{u: ("temp", Decimal(1)) for u in ("°c", "° c", "°", "degree", "degrees")},
}

HINT = "Hinweis: {n} Angabe(n) ließ(en) sich nicht belegen und wurde(n) entfernt."
NAME_HINT = (
    "Hinweis: {names} kommt in den Suchergebnissen dieser Antwort nicht vor"
    " – bitte nicht als Vorschlag verstehen."
)
NAME_HINT_PLURAL = (
    "Hinweis: {names} kommen in den Suchergebnissen dieser Antwort nicht vor"
    " – bitte nicht als Vorschlag verstehen."
)


HINT_EN = "Note: {n} figure(s) could not be verified and were removed."
NAME_HINT_EN = (
    "Note: {names} does not appear in this answer's search results"
    " – please do not take it as a suggestion."
)
NAME_HINT_PLURAL_EN = (
    "Note: {names} do not appear in this answer's search results"
    " – please do not take them as suggestions."
)


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
    unsupported_names: list[str] = field(
        default_factory=list
    )  # tour names, kept in the text with NAME_HINT


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


def _value(raw: str, lang: Lang = "de") -> tuple[Decimal, int]:
    if raw[:1] in ("-", "−"):
        value, decimals = _value(raw[1:], lang)
        return -value, decimals
    word = re.sub(r"\s+", " ", raw.lower())
    if lang == "en":
        if word in _HALVES_EN:
            return Decimal(_HALVES_EN[word]), 1
        if word in _WORDS_EN:
            return Decimal(_WORDS_EN[word]), 0
        m = re.fullmatch(r"(\w+)[-\s](\w+)", word)
        if m and m.group(1) in _WORDS_EN and m.group(2) in _WORDS_EN:  # "twenty-five"
            return Decimal(_WORDS_EN[m.group(1)] + _WORDS_EN[m.group(2)]), 0
        if word in ("a", "an"):
            return Decimal(1), 0
        if m := re.fullmatch(r"(\S+) and a half", word):
            return _value(m.group(1), lang)[0] + Decimal("0.5"), 1
        if re.fullmatch(r"\d+,\d{1,2}", raw):  # decimal comma
            raw = raw.replace(",", ".")
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", raw):  # English thousands separator
            raw = raw.replace(",", "")
        return Decimal(raw), len(raw.split(".")[1]) if "." in raw else 0
    if word in _HALVES:
        return Decimal(_HALVES[word]), 1
    if word in _WORDS:
        return Decimal(_WORDS[word]), 0
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):  # German thousands separator
        return Decimal(raw.replace(".", "")), 0
    raw = raw.replace(",", ".")
    return Decimal(raw), len(raw.split(".")[1]) if "." in raw else 0


_NOT_AFTER_A = frozenset({"m", "h", "hm", "mm", "%", "°", "mi", "ft", "yd"})


def _unit_of(text: str, m: re.Match[str], lang: Lang) -> tuple[str, Decimal]:
    unit = re.sub(r"\s+", " ", m.group("unit").lower())
    if lang == "de":
        return _UNITS[unit]
    dim, factor = _UNITS_EN[unit]
    if dim == "metre":  # the words around it may say "climb"
        before = text[max(0, m.start("num") - 40) : m.start("num")]
        if _ASCENT_BEFORE.search(before) or _ASCENT_AFTER.match(text, m.end()):
            return "ascent", factor
        if _LENGTH_AFTER.match(text, m.end()):  # "540 m long": a length, never an ascent
            return "length", factor
    return dim, factor


def _found(text: str, lang: Lang = "de") -> list[_Found]:
    out: list[_Found] = []
    pattern = _NUMBER_WITH_UNIT_EN if lang == "en" else _NUMBER_WITH_UNIT
    for m in pattern.finditer(text):
        if lang == "en" and m.group("oh") is not None:  # "9 o'clock"
            word = m.group("oh").lower()
            hour = int(word) if word.isdigit() else int(_value(word, lang)[0])
            number = _Number(Decimal(hour) * 60, 0, "clock", Decimal(1))
            out.append(_Found(number, (m.span("oh"),), m.group(0)))
            continue
        if m.group("uh") is not None:  # clock time, in minutes after midnight
            hour = int(m.group("uh"))
            if lang == "en":
                ap = (m.group("ap") or "").lower()
                hour = hour % 12 + (12 if ap.startswith("p") else 0) if ap else hour
            total = Decimal(hour) * 60 + Decimal(m.group("um") or 0)
            number = _Number(total, 0, "clock", Decimal(1))
            spans = (m.span("uh"), m.span("um")) if m.group("um") else (m.span("uh"),)
            out.append(_Found(number, spans, m.group(0)))
            continue
        if m.group("ch") is not None or m.group("kh") is not None:  # compound duration
            h, mins = ("ch", "cm") if m.group("ch") is not None else ("kh", "km")
            total = Decimal(m.group(h)) * 60 + Decimal(m.group(mins))
            number = _Number(total, 0, "time", Decimal(1))
            out.append(_Found(number, (m.span(h), m.span(mins)), m.group(0)))
            continue
        unit = m.group("unit")
        if lang == "en" and m.group("num").lower() in ("a", "an") and unit.lower() in _NOT_AFTER_A:
            continue  # the article before a letter: "a m…", not "1 m"
        dim, factor = _unit_of(text, m, lang)
        if m.group("lo") is not None and m.group("lo").lower() not in ("a", "an"):
            value, decimals = _value(m.group("lo"), lang)
            number = _Number(value, decimals, dim, factor)
            out.append(_Found(number, (m.span("lo"),), f"{m.group('lo')} {unit}"))
        value, decimals = _value(m.group("num"), lang)
        number = _Number(value, decimals, dim, factor)
        out.append(_Found(number, (m.span("num"),), text[m.start("num") : m.end()]))
    return out


def numbers_in_text(text: str, lang: Lang = "de") -> list[str]:
    return [f.shown for f in _found(text, lang)]


def _evidence_numbers(evidence: Evidence, lang: Lang = "de") -> list[_Number]:
    """Evidence read the way the answer is written; English answers also read the German form
    ("12,4 km", "540 Hm"): Evidence.add and knowledge passages are German-formatted."""
    out = [f.number for text in evidence.numbers for f in _found(text, lang)]
    if lang == "en":
        out += [f.number for text in evidence.numbers for f in _found(text, "de")]
    return out


def _round(x: Decimal, decimals: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _supported(n: _Number, known: list[_Number]) -> bool:
    """Equal after converting the evidence to the answer's unit and rounding it to the answer's
    precision. Durations count only as a whole: "2 h" or "54 min" alone is not 2,9 h."""
    return any(
        _same_dim(k.dim, n.dim) and _round(k.value * k.factor / n.factor, n.decimals) == n.value
        for k in known
    )


def _same_dim(a: str, b: str) -> bool:
    """English "metre" (a bare "m") is compatible with a length and with an ascent."""
    return a == b or {a, b} <= {"metre", "length", "ascent"} and "metre" in (a, b)


def has_number(evidence: Evidence, value: float, unit: str, lang: Lang = "de") -> bool:
    """Exactly this value (after unit conversion, no rounding) is in the evidence."""
    probe = _found(f"{float(value):.6f}".rstrip("0").rstrip(".").replace(".", ",") + f" {unit}")
    if len(probe) != 1:
        return False
    n = probe[0].number
    return any(
        k.dim == n.dim and k.value * k.factor == n.value * n.factor
        for k in _evidence_numbers(evidence, lang)
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
    answer: str,
    evidence: Evidence,
    tour_names: list[str] | tuple[str, ...] = (),
    lang: Lang = "de",
) -> GroundingResult:
    known = _evidence_numbers(evidence, lang)
    unsupported: list[str] = []
    spans: list[tuple[int, int]] = []
    for f in _found(answer, lang):
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
        hint = HINT_EN if lang == "en" else HINT
        text = text.rstrip() + "\n\n" + hint.format(n=len(unsupported))
    names = _unsupported_names(answer, evidence, list(tour_names))
    if names:
        one, many = (
            (NAME_HINT_EN, NAME_HINT_PLURAL_EN) if lang == "en" else (NAME_HINT, NAME_HINT_PLURAL)
        )
        hint = one if len(names) == 1 else many
        text = text.rstrip() + "\n\n" + hint.format(names=", ".join(names))
    return GroundingResult(text=text, unsupported=unsupported, unsupported_names=names)


# a sentence ends at . ! ? : or a line break, but not inside common abbreviations ("z. B.") and not
# at list numbering at a line start ("2. "), so a removed list item takes its number and line along
_ABBR = r"z\.\s?B\.|d\.\s?h\.|u\.\s?a\.|ca\.|bzw\.|evtl\.|ggf\.|inkl\.|usw\."
_LIST_NO = r"(?<![^\n])[ \t]*\d+\.(?=[ \t])"
_SENTENCE = re.compile(rf"(?:{_LIST_NO}|{_ABBR}|[^.!?:\n])*(?:[.!?:]+|\n|$)\s*", re.IGNORECASE)
# "Keine Tour erfüllt alle Wünsche" and its variants ("Leider erfüllt keine der Touren alle
# deine Bedingungen"): only the code may say that, and only when it fell back (spec §2 Ziel 3)
# the negation must govern the fulfilment within one clause (only words and spaces between):
# "Keine (der|dieser) (drei) Tour(en) erfüllt alle (deine) Wünsche" or "erfüllt keine der Touren alle …"
_CLAIM_NOUNS = r"(?:wünsche|bedingungen|anforderungen|kriterien|vorgaben|angaben)\b"
_CLAIM_SUBJECT = r"kein\w*(?:\s+(?:der|dieser|von\s+den))?(?:\s+\w+){0,2}"
_CLAIM_ALL = r"(?:alle|sämtliche)\w*\s+(?:\w+\s+)?" + _CLAIM_NOUNS
_UNSAT_CLAIM = re.compile(
    rf"\b{_CLAIM_SUBJECT}\s+erfüll\w*\s+(?:\w+\s+)?{_CLAIM_ALL}"
    rf"|\berfüll\w*\s+(?:\w+\s+)?{_CLAIM_SUBJECT}\s+{_CLAIM_ALL}",
    re.IGNORECASE,
)


# English: "No tour meets all your wishes", "None of the tours fulfils all of your conditions"
_EN_NOUNS = r"(?:wishes|conditions|requirements|criteria|requests|preferences)\b"
_EN_ALL = rf"all\s+(?:of\s+)?(?:(?:your|the|these|those)\s+)?(?:\w+\s+)?{_EN_NOUNS}"
_EN_THING = r"(?:tours?|walks?|hikes?|routes?|trails?|options?|suggestions?|results?|candidates?)"
_EN_SUBJECT = (
    rf"(?:no\s+(?:\w+\s+)?{_EN_THING}(?:\s+(?:that|which))?"
    rf"|none\s+of\s+(?:the|these|those|my|our)\s+(?:\w+\s+)?{_EN_THING}"
    r"|none\s+of\s+them|none)"
)
_EN_VERB = r"(?:(?:can(?:not)?|could|will)\s+)?(?:fully\s+)?"
_EN_VERB += r"(?:meets?|fulfil(?:s|ls)?|satisf(?:y|ies)|matches|match|fits?|covers?)"
_UNSAT_CLAIM_EN = re.compile(rf"\b{_EN_SUBJECT}\s+{_EN_VERB}\s+{_EN_ALL}", re.IGNORECASE)
_ABBR_EN = r"e\.\s?g\.|i\.\s?e\.|approx\.|etc\.|incl\."
# no sentence end inside a decimal number ("11.6 km")
_SENTENCE_EN = re.compile(
    rf"(?:{_LIST_NO}|{_ABBR_EN}|\d\.(?=\d)|[^.!?:\n])*(?:[.!?:]+|\n|$)\s*", re.IGNORECASE
)


def strip_unsat_claims(text: str, lang: Lang = "de") -> tuple[str, int]:
    """The text without sentences claiming no tour meets all wishes, and how many were removed."""
    sentence, claim = (_SENTENCE_EN, _UNSAT_CLAIM_EN) if lang == "en" else (_SENTENCE, _UNSAT_CLAIM)
    kept: list[str] = []
    removed = 0
    for part in sentence.findall(text):
        if claim.search(part):
            removed += 1
        else:
            kept.append(part)
    return (text, 0) if not removed else ("".join(kept).strip(), removed)


def strip_weather_claims(text: str, has_word: Callable[[str], bool], lang: Lang = "de") -> tuple[str, int]:
    """The text without sentences that contain a word of the weather wish (`has_word(sentence)`),
    and how many were removed. Used when the forecast says the wish is not met or is unknown."""
    sentence = _SENTENCE_EN if lang == "en" else _SENTENCE
    kept: list[str] = []
    removed = 0
    for part in sentence.findall(text):
        if has_word(part):
            removed += 1
        else:
            kept.append(part)
    return (text, 0) if not removed else ("".join(kept).strip(), removed)
