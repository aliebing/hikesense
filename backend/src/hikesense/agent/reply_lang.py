"""Reply language from the message itself: a German message gets a German reply, an English one an
English reply, whatever the language switch of the page says (the switch only sets the page).

Counted on whole words of a fixed list, without the model: deterministic, free and testable.
Words that both languages use ("in", "tour", "am", "an", "was", "will") and place names never
count. A message without a clear majority ("Hausach", a clicked option "Feldberg (Gipfel)" may
still decide) keeps the language of the conversation so far, else the page language."""

from __future__ import annotations

import re

from hikesense.numfmt import Lang

_GERMAN = frozenset(
    """
    ich mir mich wir uns und oder mit ohne ab um bei von nach zum zur der die das den dem des
    ein eine einen einem einer ist sind gibt es wie wo welche welcher welches bitte nicht
    kein keine keinen über unter mindestens höchstens etwa ungefähr circa ca tage tag tagen
    tägige tägigen tagestour wanderung wanderungen wandern rundweg rundwanderung runde laufen
    joggen kürzer länger kürzere längere mehr weniger wetter regen trocken morgen heute
    übermorgen übernachtung unterkunft etappe etappen für auf aus zu im vom beim hm höhenmeter
    anstieg gemeinde ort gipfel stunden std schöne schön aussicht einkehr mache mach zeig zeige
    suche finde möchte würde kann gerne wochenende woche nächste nächsten
    """.split()  # noqa: SIM905 - one readable word list
)
_ENGLISH = frozenset(
    """
    i me my we us and or with without from near around about at the a of to for on is are how
    what where which there please not no over under least most roughly approximately days day
    hike hikes hiking walk walks walking round circular loop trail shorter longer more less
    weather rain dry tomorrow today stay overnight stage stages hours hour ascent climb
    municipality village peak town lake make show find want would can could like nice view
    weekend week next run running jog jogging long short
    """.split()  # noqa: SIM905 - one readable word list
)
_WORD = re.compile(r"[a-zäöüß]+(?:'[a-z]+)?")


def detect_lang(text: str) -> Lang | None:
    """ "de" or "en" when the message's own words say so clearly, else None."""
    words = _WORD.findall(text.lower())
    de = sum(w in _GERMAN for w in words)
    en = sum(w in _ENGLISH for w in words)
    if de > en:
        return "de"
    if en > de:
        return "en"
    return None


def reply_lang(message: str, previous: Lang | None, page: Lang) -> Lang:
    """The message's language; if unclear, the conversation's so far; else the page's."""
    return detect_lang(message) or previous or page
