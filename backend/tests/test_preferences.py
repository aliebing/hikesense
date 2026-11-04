from hikesense.agent.request import Constraint, HikeRequest, Preference
from hikesense.preferences import with_saved

KNOWN = {
    "feature:aussicht",
    "feature:einkehr",
    "feature:rundweg",
    "surface:naturweg",
    "surface:gut_laufbar",
}


def saved(tag, mode="prefer", weight=2):
    return Preference(tag_id=tag, mode=mode, weight=weight, saved=True)


def req(prefs=(), constraints=()):
    return HikeRequest(intent="day_hike", preferences=list(prefs), constraints=list(constraints))


def test_saved_preferences_are_added_after_the_chat_wishes():
    r = with_saved(
        req([Preference(tag_id="feature:einkehr", mode="prefer")]),
        [saved("feature:aussicht")],
        KNOWN,
    )
    assert [(p.tag_id, p.saved) for p in r.preferences] == [
        ("feature:einkehr", False),
        ("feature:aussicht", True),
    ]


def test_the_chat_wins_for_the_same_tag():
    chat = Preference(tag_id="feature:aussicht", mode="avoid", weight=3)
    r = with_saved(req([chat]), [saved("feature:aussicht", "prefer", 5)], KNOWN)
    assert r.preferences == [chat]


def test_a_surface_wish_in_the_chat_replaces_saved_surface_preferences():
    chat = Preference(tag_id="surface:gut_laufbar", mode="prefer")
    r = with_saved(req([chat]), [saved("surface:naturweg"), saved("feature:einkehr")], KNOWN)
    assert [p.tag_id for p in r.preferences] == ["surface:gut_laufbar", "feature:einkehr"]


def test_a_round_walk_condition_makes_the_saved_round_walk_moot():
    rt = Constraint(kind="roundtrip", required=True)
    r = with_saved(req(constraints=[rt]), [saved("feature:rundweg")], KNOWN)
    assert r.preferences == []


def test_unknown_tags_are_skipped():
    assert with_saved(req(), [saved("feature:weg")], KNOWN).preferences == []
