"""Input sanitising, a prompt-injection heuristic and a system-prompt leak check."""

from __future__ import annotations

import re

from hikeall.regions import REGION_NAMES

INJECTION_REPLY = (
    "Dabei kann ich nicht helfen. Frag mich gern nach Wanderungen oder Laufrunden "
    f"({REGION_NAMES})."
)
RATE_LIMIT_REPLY = "Zu viele Anfragen – bitte in {s} Sekunden noch einmal."

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INLINE_SPACE = re.compile(r"[ \t]+")
_ZERO_WIDTH = re.compile("[\u200b-\u200d\u2060\ufeff]")
_WS = re.compile(r"\s+")
_ADJ = r"(?:all|any|the|your|my|these|those|previous|prior|above|earlier)"
_DE_ADJ = r"(?:alle|alles|die|deine|diese|jegliche|vorherigen|vorigen|bisherigen|obigen|bisherige)"
_ROLE_EN = r"(?:assistant|ai|dan|model|bot|chatbot|unrestricted|jailbroken|evil)"
_ROLE_DE = r"(?:assistent\w*|ki|dan|modell|bot|chatbot|uneingeschr\w+|ohne regeln)"
_INJECTION = [
    re.compile(p, re.IGNORECASE)
    for p in (
        rf"\b(?:ignore|disregard|forget)\s+(?:{_ADJ}\s+)+(?:instructions|prompts|rules)\b",
        r"\b(?:reveal|print|show|repeat)(?: me)? (?:your (?:system )?|the system )(?:prompt|instructions)\b",
        r"\bsystem[ -]?prompt\b",
        r"\bapi[ _-]?(?:key|schl\u00fcssel|schluessel)\b",
        rf"\byou are now (?:an? |the )?(?:\w+ ){{0,2}}?{_ROLE_EN}\b",
        r"\bpretend (?:to be|you are) (?:an? )?(?:\w+ ){0,2}?(?:unrestricted|jailbroken|without rules)",
        # German
        rf"\b(?:ignorier\w*|vergiss|missachte\w*)\s+(?:{_DE_ADJ}\s+)+(?:anweisungen|instruktionen|regeln|befehle)\b",
        (
            r"\b(?:zeig|zeige|verrate|wiederhole|nenne|gib)(?: mir)? (?:deinen|deine|dein) "
            r"(?:system[ -]?prompt|anweisungen|instruktionen)\b"
        ),
        rf"\bdu bist (?:jetzt|nun|ab jetzt) (?:ein |eine |der |die )?(?:\w+ ){{0,2}}?{_ROLE_DE}",
    )
]


def sanitize_text(text: str, max_chars: int = 1000) -> str:
    return _INLINE_SPACE.sub(" ", _CONTROL.sub("", _ZERO_WIDTH.sub("", text))).strip()[:max_chars]


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION)


def leaks_system_prompt(answer: str, system_prompt: str, min_overlap: int = 60) -> bool:
    """True if a contiguous piece of >= min_overlap chars of the prompt appears in the answer."""
    sp = _WS.sub(" ", system_prompt).strip()
    ans = _WS.sub(" ", answer)
    if len(sp) < min_overlap:
        return bool(sp) and sp in ans
    return any(sp[i : i + min_overlap] in ans for i in range(len(sp) - min_overlap + 1))
