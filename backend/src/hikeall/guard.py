"""Input sanitising, a prompt-injection heuristic and a system-prompt leak check."""

from __future__ import annotations

import re

INJECTION_REPLY = (
    "Dabei kann ich nicht helfen. Frag mich gern nach Wanderungen oder Laufrunden im Schwarzwald."
)
RATE_LIMIT_REPLY = "Zu viele Anfragen – bitte in {s} Sekunden noch einmal."

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INLINE_SPACE = re.compile(r"[ \t]+")
_WS = re.compile(r"\s+")
_INJECTION = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts|rules)",
        r"disregard (the |your |all )?(rules|instructions)",
        r"(reveal|print|show|repeat) (me )?(your|the) (system )?(prompt|instructions)",
        r"\bsystem[ -]?prompt\b",
        r"\bapi[ _-]?(key|schlüssel|schluessel)\b",
        r"\byou are now\b",
        # German
        (
            r"ignorier\w* (alle |die )?(vorherigen|vorigen|bisherigen|obigen) "
            r"(anweisungen|instruktionen|regeln|befehle)"
        ),
        r"vergiss (alle |die )?(vorherigen|bisherigen|obigen|deine) (anweisungen|instruktionen|regeln)",
        (
            r"(zeig|zeige|verrate|wiederhole|nenne|gib)( mir)? (deinen|den|deine|die) "
            r"(system[ -]?prompt|anweisungen|instruktionen)"
        ),
        r"\bdu bist (jetzt|nun|ab jetzt)\b",
    )
]


def sanitize_text(text: str, max_chars: int = 1000) -> str:
    return _INLINE_SPACE.sub(" ", _CONTROL.sub("", text)).strip()[:max_chars]


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION)


def leaks_system_prompt(answer: str, system_prompt: str, min_overlap: int = 60) -> bool:
    """True if a contiguous piece of >= min_overlap chars of the prompt appears in the answer."""
    sp = _WS.sub(" ", system_prompt).strip()
    ans = _WS.sub(" ", answer)
    if len(sp) < min_overlap:
        return bool(sp) and sp in ans
    return any(sp[i : i + min_overlap] in ans for i in range(len(sp) - min_overlap + 1))
