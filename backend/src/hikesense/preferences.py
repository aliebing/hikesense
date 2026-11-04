"""Standing preferences of a signed-in user ("Vorlieben", table user_preferences).

They are added to a day-hike search like chat wishes, marked `saved`, and only re-sort the
results (constraints.preference_score). Whatever the chat says about a tag wins: a saved
preference is left out when the request already has a wish for that tag, a surface wish (the
surface tags are alternatives) or a round-walk condition.
"""

from __future__ import annotations

import psycopg

from hikesense.agent.request import MAX_PREFERENCES, HikeRequest, Preference

ROUNDTRIP_TAG = "feature:rundweg"


def load_saved(conn: psycopg.Connection, user_id: str) -> list[Preference]:
    """The user's saved preferences, most important first."""
    rows = conn.execute(
        "select tag_id, mode, weight from user_preferences where user_id = %s "
        "order by weight desc, tag_id",
        (user_id,),
    ).fetchall()
    return [Preference(tag_id=t, mode=m, weight=w, saved=True) for t, m, w in rows]


def with_saved(req: HikeRequest, saved: list[Preference], known: set[str]) -> HikeRequest:
    """`req` plus the saved preferences the chat did not already decide; `known` are the tag ids
    of the vocabulary (a saved tag that no longer exists is skipped)."""
    have = {p.tag_id for p in req.preferences}
    surface_wish = any(p.tag_id.startswith("surface:") and not p.saved for p in req.preferences)
    roundtrip = any(c.kind == "roundtrip" for c in req.constraints)
    added = [
        p
        for p in saved
        if p.tag_id in known
        and p.tag_id not in have
        and not (surface_wish and p.tag_id.startswith("surface:"))
        and not (roundtrip and p.tag_id == ROUNDTRIP_TAG)
    ]
    room = MAX_PREFERENCES - len(req.preferences)
    if not added or room <= 0:
        return req
    return req.model_copy(update={"preferences": [*req.preferences, *added[:room]]})
