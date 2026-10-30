"""German number formatting for every number the code shows the model or the user.

Rounds half-up on the decimal text, the same rule the grounding check uses for its evidence
(agent/grounding.py `_round`): round(4.35, 1) would give 4.3 (binary float), the check 4,4.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def _quantize(x: float, decimals: int) -> Decimal:
    # the same 6-decimal text the evidence is built from (grounding.Evidence.add)
    return Decimal(f"{float(x):.6f}").quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def round_half_up(x: float, decimals: int = 0) -> float:
    """Half-up (away from zero at .5) instead of Python's round-half-even on binary floats."""
    q = _quantize(x, decimals)
    return int(q) if decimals == 0 else float(q)


def de(x: float, decimals: int = 1) -> str:
    """German number with comma, at most `decimals` decimals, without trailing zeros."""
    s = f"{_quantize(x, decimals):.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").removesuffix(".")
    return s.replace(".", ",")
