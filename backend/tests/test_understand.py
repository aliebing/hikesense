import pytest

from hikeall.agent.request import (
    Clarify,
    Constraint,
    HikeRequest,
    Preference,
    RawRequest,
    RawWish,
    ResolvedStart,
)
from hikeall.agent.understand import echo, understand
from hikeall.llm.gateway import FakeGateway
from hikeall.tags.vocabulary import FEATURES_YAML, Attribute, NearPlace, Tag, TagVocabulary


def _place(tid: str, label: str, lat: float, lon: float, pid: int) -> Tag:
    return Tag(
        id=tid,
        label=label,
        category="place",
        rule=NearPlace(place_id=pid, radius_km=15, lat=lat, lon=lon),
    )


@pytest.fixture
def vocab() -> TagVocabulary:
    places = [
        _place("place:feldberg", "Feldberg", 47.8741, 8.0038, 1),
        _place("place:feldberg-schwarzwald", "Feldberg (Schwarzwald)", 47.86, 8.04, 2),
        _place("place:todtnau", "Todtnau", 47.83, 7.95, 3),
        _place("place:titisee-neustadt", "Titisee-Neustadt", 47.9, 8.2, 4),
        _place("place:hinterzarten", "Hinterzarten", 47.9, 8.1, 5),
    ]
    return TagVocabulary(TagVocabulary.from_features(FEATURES_YAML).all() + places)


def raw(**kw) -> RawRequest:
    kw.setdefault("intent", "day_hike")
    return RawRequest(**kw)


def gw_of(**kw) -> FakeGateway:
    return FakeGateway(structured={RawRequest: [raw(**kw)]})


def kinds(req: HikeRequest) -> dict[str, Constraint]:
    return {c.kind: c for c in req.constraints}


def test_feldberg_case_keeps_all_three_constraints(vocab):
    gw = gw_of(
        start_text="Feldberg (Schwarzwald)", roundtrip=True, ascent_m_max=200, length_km_min=15
    )
    req = understand(gw, vocab, "Rundweg, unter 200 Hm, über 15 km, Feldberg", None)
    assert isinstance(req, HikeRequest)
    assert set(kinds(req)) == {"roundtrip", "ascent_m", "length_km", "radius_km"}
    assert kinds(req)["radius_km"].max == 15.0
    assert req.start.tag_id == "place:feldberg-schwarzwald"
    assert (req.start.lat, req.start.lon) == (47.86, 8.04)


def test_explicit_radius_is_kept(vocab):
    req = understand(gw_of(start_text="Todtnau", radius_km_max=8), vocab, "x", None)
    assert kinds(req)["radius_km"].max == 8


def test_ambiguous_place_asks(vocab):
    res = understand(gw_of(start_text="Feldberg"), vocab, "Tour am Feldberg", None)
    assert isinstance(res, Clarify)
    assert set(res.options) == {"Feldberg", "Feldberg (Schwarzwald)"}


def test_unknown_place_asks_with_suggestions(vocab):
    res = understand(gw_of(start_text="Hinterzarden"), vocab, "Tour", None)
    assert isinstance(res, Clarify)
    assert "Hinterzarten" in res.options and len(res.options) <= 3


def test_area_start_has_bbox_and_no_default_radius(vocab):
    req = understand(gw_of(start_text="Südschwarzwald"), vocab, "x", None)
    assert req.start.kind == "area" and req.start.bbox is not None
    assert "radius_km" not in kinds(req)


def test_unknown_wish_is_reported_not_dropped(vocab):
    req = understand(
        gw_of(start_text="Todtnau", wishes=[RawWish(text="Kinderwagen")]), vocab, "...", None
    )
    assert req.unmatched == ["Kinderwagen"]
    assert req.preferences == []
    assert "Kinderwagen" in echo(req, vocab)


def test_known_wish_becomes_preference_with_clamped_weight(vocab):
    wishes = [RawWish(text="Aussicht", weight=9), RawWish(text="Bahnhof", mode="avoid")]
    req = understand(gw_of(start_text="Todtnau", wishes=wishes), vocab, "x", None)
    assert req.preferences == [
        Preference(tag_id="feature:aussicht", mode="prefer", weight=5),
        Preference(tag_id="feature:bahnhof", mode="avoid", weight=3),
    ]


def test_more_than_ten_wishes_overflow_to_unmatched(vocab):
    extra = [
        Tag(
            id=f"feature:extra{i}",
            label=f"Extra{i}",
            category="feature",
            rule=Attribute(roundtrip=True),
        )
        for i in range(4)
    ]
    vocab = TagVocabulary(vocab.all() + extra)
    tags = [t for t in vocab.all() if t.category in ("feature", "surface")]
    assert len(tags) > 10
    wishes = [RawWish(text=t.label) for t in tags]
    req = understand(gw_of(start_text="Todtnau", wishes=wishes), vocab, "x", None)
    assert len(req.preferences) == 10
    assert len(req.unmatched) == len(tags) - 10


def test_run_gets_runnable_preference(vocab):
    req = understand(gw_of(activity="run", start_text="Todtnau"), vocab, "x", None)
    assert Preference(tag_id="surface:gut_laufbar", mode="prefer", weight=3) in req.preferences
    assert "Vorlieben: Gut laufbar (Gewicht 3)" in echo(req, vocab)


def test_run_keeps_user_surface_wish(vocab):
    wishes = [RawWish(text="gut laufbar", mode="prefer", weight=5)]
    req = understand(gw_of(activity="run", start_text="Todtnau", wishes=wishes), vocab, "x", None)
    assert [p.weight for p in req.preferences if p.tag_id == "surface:gut_laufbar"] == [5]


def test_hike_gets_no_surface_preference(vocab):
    req = understand(gw_of(start_text="Todtnau"), vocab, "x", None)
    assert req.preferences == []


def test_run_duration_without_pace_asks(vocab):
    res = understand(
        gw_of(activity="run", start_text="Todtnau", duration_h_max=1), vocab, "x", None
    )
    assert res == Clarify(question="Welches Tempo läufst du ungefähr (min/km)?", options=[])


def test_run_duration_with_pace_is_fine(vocab):
    res = understand(
        gw_of(activity="run", start_text="Todtnau", duration_h_max=1, pace_min_per_km=6),
        vocab,
        "x",
        None,
    )
    assert isinstance(res, HikeRequest) and res.pace_min_per_km == 6


def _previous(vocab) -> HikeRequest:
    return understand(
        gw_of(start_text="Todtnau", roundtrip=True, length_km_max=10, ascent_m_max=400),
        vocab,
        "x",
        None,
    )


def test_change_replaces_only_same_kind(vocab):
    prev = _previous(vocab)
    res = understand(gw_of(intent="change", length_km_max=6), vocab, "kürzer bitte", prev)
    assert isinstance(res, HikeRequest)
    c = kinds(res)
    assert c["length_km"].max == 6
    assert c["ascent_m"].max == 400 and c["roundtrip"].required is True
    assert c["radius_km"].max == 15.0
    assert res.start == prev.start
    assert prev.constraints != res.constraints  # previous untouched
    assert kinds(prev)["length_km"].max == 10


def test_change_can_replace_start_and_adds_wishes(vocab):
    prev = _previous(vocab)
    res = understand(
        gw_of(intent="change", start_text="Hinterzarten", wishes=[RawWish(text="Aussicht")]),
        vocab,
        "x",
        prev,
    )
    assert res.start.tag_id == "place:hinterzarten"
    assert [p.tag_id for p in res.preferences] == ["feature:aussicht"]


def test_change_without_previous_request_asks(vocab):
    res = understand(gw_of(intent="change", length_km_max=6), vocab, "kürzer bitte", None)
    assert isinstance(res, Clarify)
    assert res.question.startswith("Worauf bezieht sich die Änderung?")


def test_knowledge_question_needs_no_place(vocab):
    req = understand(gw_of(intent="knowledge", question="Was ist ein Bannwald?"), vocab, "x", None)
    assert isinstance(req, HikeRequest) and req.start is None and req.constraints == []
    assert req.question == "Was ist ein Bannwald?"


def test_echo_lists_every_constraint_and_unmatched(vocab):
    req = HikeRequest(
        intent="day_hike",
        start_text="Feldberg (Schwarzwald)",
        start=ResolvedStart(
            kind="place", tag_id="place:feldberg-schwarzwald", label="Feldberg (Schwarzwald)"
        ),
        constraints=[
            Constraint(kind="roundtrip", required=True),
            Constraint(kind="length_km", min=15),
            Constraint(kind="ascent_m", max=200),
            Constraint(kind="duration_h", min=2, max=3),
            Constraint(kind="radius_km", max=15),
        ],
        preferences=[
            Preference(tag_id="feature:aussicht", mode="prefer", weight=4),
            Preference(tag_id="feature:bahnhof", mode="avoid", weight=3),
        ],
        unmatched=["Kinderwagen"],
    )
    text = echo(req, vocab)
    assert text.startswith("Verstanden:")
    for part in (
        "Feldberg (Schwarzwald)",
        "Rundweg",
        "mindestens 15 km",
        "höchstens 200 Hm",
        "2–3 h",
        "Umkreis höchstens 15 km",
        "Aussicht",
        "Bahnhof",
        "nicht prüfbar: Kinderwagen",
    ):
        assert part in text


def _dup_vocab(vocab):
    def tag(tid, kind, pid):
        return Tag(
            id=tid,
            label="Dupberg",
            category="place",
            rule=NearPlace(place_id=pid, radius_km=15, lat=47.8, lon=8.0, kind=kind),
        )

    return TagVocabulary(
        vocab.all() + [tag("place:dupberg", "peak", 7), tag("place:dupberg-n8", "town", 8)]
    )


def test_same_tag_same_mode_keeps_max_weight(vocab):
    wishes = [RawWish(text="Aussicht", weight=2), RawWish(text="Panorama", weight=4)]
    req = understand(gw_of(start_text="Todtnau", wishes=wishes), vocab, "x", None)
    assert req.preferences == [Preference(tag_id="feature:aussicht", mode="prefer", weight=4)]
    assert req.unmatched == []


def test_same_tag_opposite_modes_applies_neither_and_reports(vocab):
    wishes = [RawWish(text="Aussicht"), RawWish(text="Panorama", mode="avoid")]
    req = understand(gw_of(start_text="Todtnau", wishes=wishes), vocab, "x", None)
    assert req.preferences == []
    assert req.unmatched == ["Aussicht: bevorzugen und meiden zugleich"]


def test_change_overflow_reports_label_not_id(vocab):
    extra = [
        Tag(
            id=f"feature:x{i}", label=f"Xtra{i}", category="feature", rule=Attribute(roundtrip=True)
        )
        for i in range(11)
    ]
    v = TagVocabulary(vocab.all() + extra)
    prev = HikeRequest(
        intent="day_hike",
        preferences=[Preference(tag_id=f"feature:x{i}", mode="prefer") for i in range(10)],
    )
    res = understand(gw_of(intent="change", wishes=[RawWish(text="Xtra10")]), v, "x", prev)
    assert len(res.preferences) == 10
    assert res.unmatched == ["Xtra10"]


@pytest.mark.parametrize(
    "field,label",
    [
        ("length_km_max", "Länge"),
        ("ascent_m_max", "Anstieg"),
        ("duration_h_max", "Dauer"),
        ("radius_km_max", "Umkreis"),
    ],
)
def test_non_positive_value_is_reported_not_applied(vocab, field, label):
    req = understand(gw_of(start_text="Todtnau", **{field: -5}), vocab, "x", None)
    assert f"{label}: -5 ist kein gültiger Wert" in req.unmatched
    kind = field.rsplit("_", 1)[0]
    kind = {"length_km": "length_km", "ascent_m": "ascent_m", "duration_h": "duration_h"}.get(
        kind, "radius_km"
    )
    c = kinds(req).get(kind)
    assert c is None or c.max == 15.0  # only the default radius may exist


def test_zero_pace_is_invalid_and_run_asks_again(vocab):
    res = understand(
        gw_of(activity="run", start_text="Todtnau", duration_h_max=1, pace_min_per_km=0),
        vocab,
        "x",
        None,
    )
    assert isinstance(res, Clarify) and "Tempo" in res.question
    req = understand(gw_of(start_text="Todtnau", pace_min_per_km=0), vocab, "x", None)
    assert req.pace_min_per_km is None
    assert "Tempo: 0 ist kein gültiger Wert" in req.unmatched


def test_min_greater_than_max_stays_a_constraint(vocab):
    req = understand(
        gw_of(start_text="Todtnau", length_km_min=10, length_km_max=5), vocab, "x", None
    )
    c = kinds(req)["length_km"]
    assert (c.min, c.max) == (10, 5)


def test_identical_labels_get_kind_and_answer_resolves(vocab):
    v = _dup_vocab(vocab)
    res = understand(gw_of(start_text="Dupberg"), v, "x", None)
    assert isinstance(res, Clarify)
    assert set(res.options) == {"Dupberg (Gipfel)", "Dupberg (Ort)"}
    req = understand(gw_of(start_text="Dupberg (Gipfel)"), v, "x", None)
    assert req.start.tag_id == "place:dupberg"


def test_change_surface_wish_removes_run_default(vocab):
    prev = understand(gw_of(activity="run", start_text="Todtnau"), vocab, "x", None)
    assert any(p.tag_id == "surface:gut_laufbar" for p in prev.preferences)
    res = understand(gw_of(intent="change", wishes=[RawWish(text="Naturweg")]), vocab, "x", prev)
    assert [p.tag_id for p in res.preferences] == ["surface:naturweg"]
