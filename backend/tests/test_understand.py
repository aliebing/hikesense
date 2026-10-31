from datetime import date, time

import pytest

from hikeall.agent.request import (
    Clarify,
    Constraint,
    DayChange,
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
        _place("place:hausach", "Hausach", 48.2836, 8.175, 6),
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
    req = understand(gw_of(start_text="Todtnau", radius_km_max=8), vocab, "Radius 8 km", None)
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
    rundweg = "feature:rundweg"  # the roundtrip wish is a fixed condition, not a preference (I-7)
    tags = [t for t in vocab.all() if t.category in ("feature", "surface") and t.id != rundweg]
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
        gw_of(activity="run", start_text="Todtnau", duration_h_max=1), vocab, "1 h", None
    )
    assert res == Clarify(question="Welches Tempo läufst du ungefähr (min/km)?", options=[])


def test_run_duration_with_pace_is_fine(vocab):
    res = understand(
        gw_of(activity="run", start_text="Todtnau", duration_h_max=1, pace_min_per_km=6),
        vocab,
        "1 h bei 6 min/km",
        None,
    )
    assert isinstance(res, HikeRequest) and res.pace_min_per_km == 6


def _previous(vocab) -> HikeRequest:
    return understand(
        gw_of(start_text="Todtnau", roundtrip=True, length_km_max=10, ascent_m_max=400),
        vocab,
        "Rundweg unter 10 km und 400 Hm",
        None,
    )


def test_change_replaces_only_same_kind(vocab):
    prev = _previous(vocab)
    res = understand(gw_of(intent="change", length_km_max=6), vocab, "höchstens 6 km", prev)
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
    req = understand(gw_of(start_text="Todtnau", **{field: -5}), vocab, "-5", None)
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
        "1 h, Tempo 0",
        None,
    )
    assert isinstance(res, Clarify) and "Tempo" in res.question
    req = understand(gw_of(start_text="Todtnau", pace_min_per_km=0), vocab, "Tempo 0", None)
    assert req.pace_min_per_km is None
    assert "Tempo: 0 ist kein gültiger Wert" in req.unmatched


def test_min_greater_than_max_stays_a_constraint(vocab):
    req = understand(
        gw_of(start_text="Todtnau", length_km_min=10, length_km_max=5), vocab, "10 bis 5 km", None
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


# --- final fix wave (R20) ----------------------------------------------------------------------


def _kind_vocab(vocab):
    def tag(tid, label, kind, pid):
        rule = NearPlace(place_id=pid, radius_km=15, lat=47.8, lon=8.0, kind=kind)
        return Tag(id=tid, label=label, category="place", rule=rule)

    others = [t for t in vocab.all() if not t.id.startswith("place:feldberg")]
    return TagVocabulary(
        others
        + [
            tag("place:feldberg", "Feldberg", "peak", 1),
            tag("place:feldberg-schwarzwald", "Feldberg (Schwarzwald)", "village", 2),
        ]
    )


def test_same_base_name_options_name_their_kind(vocab):
    v = _kind_vocab(vocab)
    res = understand(gw_of(start_text="Feldberg"), v, "Tour am Feldberg", None)
    assert isinstance(res, Clarify)
    assert res.options == ["Feldberg (Gipfel)", "Feldberg (Schwarzwald) – Ort"]


@pytest.mark.parametrize(
    ("answer", "tag_id"),
    [
        ("Feldberg (Gipfel)", "place:feldberg"),
        ("Feldberg (Schwarzwald) – Ort", "place:feldberg-schwarzwald"),
        ("Feldberg (Schwarzwald)", "place:feldberg-schwarzwald"),
    ],
)
def test_decorated_and_plain_option_both_resolve(vocab, answer, tag_id):
    from hikeall.agent.understand import resolve_option

    v = _kind_vocab(vocab)
    assert resolve_option(v, answer).tag_id == tag_id
    req = understand(gw_of(start_text=answer), v, "x", None)
    assert req.start.tag_id == tag_id


@pytest.mark.parametrize(
    ("kw", "lo", "hi", "approx"),
    [
        ({"length_km_approx": 8}, 6.8, 9.2, 8),
        ({"length_km_min": 8, "length_km_max": 8}, 6.8, 9.2, 8),
        ({"duration_h_approx": 2}, 1.7, 2.3, 2),
    ],
)
def test_single_value_becomes_visible_band(vocab, kw, lo, hi, approx):
    req = understand(gw_of(start_text="Todtnau", **kw), vocab, "8 km oder 2 h", None)
    c = next(c for c in req.constraints if c.kind in ("length_km", "duration_h"))
    assert (c.min, c.max, c.approx) == (lo, hi, approx)
    unit = "km" if c.kind == "length_km" else "h"
    label = "Länge" if c.kind == "length_km" else "Dauer"
    band = f"{str(lo).replace('.', ',')}–{str(hi).replace('.', ',')} {unit}"
    assert f"{label} {band} (≈ {approx} {unit})" in echo(req, vocab)


@pytest.mark.parametrize(
    "kw", [{"ascent_m_approx": 400}, {"ascent_m_min": 400, "ascent_m_max": 400}]
)
def test_single_ascent_value_is_a_maximum(vocab, kw):
    req = understand(gw_of(start_text="Todtnau", **kw), vocab, "400 Hm", None)
    c = kinds(req)["ascent_m"]
    assert (c.min, c.max) == (None, 400)
    assert "Anstieg höchstens 400 Hm" in echo(req, vocab)


def test_prompt_defines_single_values():
    from hikeall.agent.understand import SYSTEM_PROMPT

    assert "length_km_approx" in SYSTEM_PROMPT and "ascent_m_approx" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    ("text", "mode", "required"),
    [
        ("Rundweg", "prefer", True),
        ("Runde", "prefer", True),
        ("Rundtour", "prefer", True),
        ("Rundwanderung", "prefer", True),
        ("Laufrunde", "prefer", True),
        ("Rundweg", "avoid", False),
    ],
)
def test_roundtrip_wish_is_a_fixed_condition(vocab, text, mode, required):
    wishes = [RawWish(text=text, mode=mode, weight=2)]
    req = understand(gw_of(start_text="Todtnau", wishes=wishes), vocab, "x", None)
    assert kinds(req)["roundtrip"].required is required
    assert not any(p.tag_id == "feature:rundweg" for p in req.preferences)
    assert text not in req.unmatched


def test_roundtrip_wish_and_field_are_not_duplicated(vocab):
    wishes = [RawWish(text="Runde")]
    req = understand(gw_of(start_text="Todtnau", roundtrip=True, wishes=wishes), vocab, "x", None)
    assert [c.kind for c in req.constraints].count("roundtrip") == 1


def test_water_is_not_a_waterfall(vocab):
    req = understand(gw_of(start_text="Todtnau", wishes=[RawWish(text="Wasser")]), vocab, "x", None)
    assert req.preferences == [] and req.unmatched == ["Wasser"]


def test_feldberg_peak_village_and_municipality_are_distinct_options(vocab):
    def tag(tid, label, kind, pid, lat):
        rule = NearPlace(place_id=pid, radius_km=15, lat=lat, lon=8.0, kind=kind)
        return Tag(id=tid, label=label, category="place", rule=rule)

    others = [t for t in vocab.all() if not t.id.startswith("place:feldberg")]
    v = TagVocabulary(
        others
        + [
            tag("place:feldberg", "Feldberg", "peak", 1, 47.87),
            tag("place:feldberg-n1", "Feldberg", "village", 2, 47.5),  # far away village
            tag("place:feldberg-schwarzwald", "Feldberg (Schwarzwald)", "municipality", 3, 47.86),
        ]
    )
    res = understand(gw_of(start_text="Feldberg"), v, "Tour am Feldberg", None)
    assert isinstance(res, Clarify)
    assert len(res.options) == 3 == len(set(res.options))
    assert any("Gipfel" in o for o in res.options)
    assert any("Gemeinde" in o for o in res.options)


# --- R25: same-name municipality and village are one start ---------------------------------


def _places_vocab(vocab, *places):
    others = [t for t in vocab.all() if t.category != "place"]
    tags = [
        Tag(
            id=tid,
            label=label,
            category="place",
            rule=NearPlace(place_id=i, radius_km=15, lat=lat, lon=lon, kind=kind),
        )
        for i, (tid, label, kind, lat, lon) in enumerate(places, 1)
    ]
    return TagVocabulary(others + tags)


def test_municipality_next_to_same_name_village_is_one_start(vocab):
    v = _places_vocab(
        vocab,
        ("place:hinterzarten", "Hinterzarten", "village", 47.906, 8.104),
        ("place:hinterzarten-r1", "Hinterzarten", "municipality", 47.893, 8.090),
    )
    res = understand(gw_of(start_text="Hinterzarten"), v, "um Hinterzarten", None)
    assert not isinstance(res, Clarify)
    assert res.start.tag_id == "place:hinterzarten"


def test_far_same_name_places_stay_ambiguous(vocab):
    v = _places_vocab(
        vocab,
        ("place:feldberg", "Feldberg", "peak", 47.874, 8.005),
        ("place:feldberg-n1", "Feldberg", "village", 47.773, 7.641),
        ("place:feldberg-schwarzwald", "Feldberg (Schwarzwald)", "municipality", 47.865, 8.067),
    )
    res = understand(gw_of(start_text="Feldberg"), v, "x", None)
    assert isinstance(res, Clarify)
    assert len(res.options) == 3
    assert any("Gipfel" in o for o in res.options)
    assert any("Gemeinde" in o for o in res.options)


def test_municipality_alone_resolves(vocab):
    v = _places_vocab(
        vocab, ("place:titisee-neustadt", "Titisee-Neustadt", "municipality", 47.9, 8.2)
    )
    res = understand(gw_of(start_text="Titisee-Neustadt"), v, "x", None)
    assert not isinstance(res, Clarify)
    assert res.start.tag_id == "place:titisee-neustadt"


def test_lake_next_to_same_name_village_is_one_start(vocab):
    v = _places_vocab(
        vocab,
        ("place:titisee-n1", "Titisee", "village", 47.901, 8.150),
        ("place:titisee", "Titisee", "lake", 47.894, 8.145),
    )
    res = understand(gw_of(start_text="Titisee"), v, "x", None)
    assert not isinstance(res, Clarify)
    assert res.start.tag_id == "place:titisee-n1"


def test_lake_alone_resolves(vocab):
    v = _places_vocab(vocab, ("place:schluchsee", "Schluchsee", "lake", 47.82, 8.17))
    res = understand(gw_of(start_text="Schluchsee"), v, "x", None)
    assert not isinstance(res, Clarify)
    assert res.start.tag_id == "place:schluchsee"


# --- R27: numbers the model invented are discarded, numbers the user wrote are kept ----------


def test_model_invented_numbers_are_discarded(vocab):
    gw = gw_of(
        activity="run",
        start_text="Titisee",
        length_km_approx=8,
        ascent_m_max=0,
        duration_h_approx=1.0,
        pace_min_per_km=0,
    )
    req = understand(gw, vocab, "Laufrunde 8 km ab Titisee, wenig Asphalt", None)
    assert isinstance(req, HikeRequest)  # no Clarify for the pace
    assert set(kinds(req)) == {"length_km", "radius_km"}
    assert kinds(req)["length_km"].approx == 8
    assert req.pace_min_per_km is None
    assert not any("kein gültiger Wert" in u for u in req.unmatched)
    assert req.discarded_model_numbers == 3


@pytest.mark.parametrize(
    "message,field,value",
    [
        ("Tour über 10–14 km", "length_km_min", 14),
        ("Tour 10-14 km", "length_km_min", 10),
        ("etwa 2,5 Stunden", "duration_h_approx", 2.5),
        ("etwa 2.5 Stunden", "duration_h_approx", 2.5),
        ("drei Stunden", "duration_h_approx", 3),
        ("zwölf Kilometer", "length_km_approx", 12),
        ("zwanzig km", "length_km_approx", 20),
        ("eine Stunde", "duration_h_approx", 1),
        ("30 Minuten", "duration_h_approx", 0.5),
        ("unter 1.000 Hm", "ascent_m_max", 1000),
        ("zweieinhalb Stunden", "duration_h_approx", 2.5),
        ("eineinhalb Stunden", "duration_h_approx", 1.5),
        ("dreieinhalb Stunden", "duration_h_approx", 3.5),
        ("anderthalb Stunden", "duration_h_approx", 1.5),
        ("fünfundzwanzig km", "length_km_approx", 25),
        ("einundzwanzig km", "length_km_approx", 21),
        ("einhundert km", "length_km_approx", 100),
        ("zweihundert Hm", "ascent_m_approx", 200),
        ("tausend Hm", "ascent_m_approx", 1000),
        ("2h30", "duration_h_approx", 2.5),
        ("2 h 30", "duration_h_approx", 2.5),
        ("2 1/2 Stunden", "duration_h_approx", 2.5),
        ("1/2 Stunde", "duration_h_approx", 0.5),
        ("3/4 Stunde", "duration_h_approx", 0.75),
        ("viertel Stunde", "duration_h_approx", 0.25),
        ("halbe Stunde", "duration_h_approx", 0.5),
        ("dreiviertel Stunde", "duration_h_approx", 0.75),
    ],
)
def test_numbers_the_user_wrote_are_accepted(vocab, message, field, value):
    req = understand(gw_of(start_text="Todtnau", **{field: value}), vocab, message, None)
    assert isinstance(req, HikeRequest)
    assert req.discarded_model_numbers == 0
    assert any(c.kind == field.rsplit("_", 1)[0] for c in req.constraints)


def test_unreadable_number_expression_is_reported_not_silent(vocab):
    req = understand(
        gw_of(start_text="Todtnau", duration_h_approx=7),
        vocab,
        "etwa eine drittel Stunde",
        None,
    )
    assert "duration_h" not in kinds(req)
    assert req.discarded_model_numbers == 1
    assert "Dauer: Angabe nicht sicher erkannt – bitte als Zahl angeben" in req.unmatched


def test_pace_5_30_wrong_model_conversion_uses_parsed_value(vocab):
    gw = gw_of(start_text="Titisee", activity="run", duration_h_approx=1, pace_min_per_km=5.3)
    req = understand(gw, vocab, "Laufrunde 1 Stunde ab Titisee, Tempo 5:30", None)
    assert isinstance(req, HikeRequest)
    assert req.pace_min_per_km == 5.5
    assert req.discarded_model_numbers == 0


def test_pace_5_30_model_value_55_is_accepted(vocab):
    gw = gw_of(start_text="Titisee", activity="run", duration_h_approx=1, pace_min_per_km=5.5)
    req = understand(gw, vocab, "Laufrunde 1 Stunde ab Titisee, 5:30 min/km", None)
    assert req.pace_min_per_km == 5.5 and req.discarded_model_numbers == 0


def test_number_not_in_message_is_discarded_even_if_positive(vocab):
    req = understand(gw_of(start_text="Todtnau", ascent_m_max=500), vocab, "Rundweg Todtnau", None)
    assert "ascent_m" not in kinds(req)
    assert req.discarded_model_numbers == 1 and req.unmatched == []


def test_user_written_zero_still_reports_invalid_value(vocab):
    req = understand(gw_of(start_text="Todtnau", ascent_m_max=0), vocab, "unter 0 Hm", None)
    assert "Anstieg: 0 ist kein gültiger Wert" in req.unmatched
    assert req.discarded_model_numbers == 0


def test_invalid_value_reported_once(vocab):
    req = understand(
        gw_of(start_text="Todtnau", ascent_m_min=0, ascent_m_max=0, ascent_m_approx=0),
        vocab,
        "0 Hm",
        None,
    )
    assert req.unmatched == ["Anstieg: 0 ist kein gültiger Wert"]


def test_change_turn_with_number_in_message_still_works(vocab):
    prev = _previous(vocab)
    res = understand(
        gw_of(intent="change", ascent_m_max=300, duration_h_max=2),
        vocab,
        "und höchstens 300 Hm",
        prev,
    )
    c = kinds(res)
    assert c["ascent_m"].max == 300
    assert "duration_h" not in c  # invented, discarded
    assert c["length_km"].max == 10 and res.start == prev.start
    assert res.discarded_model_numbers == 1


def test_pace_written_by_user_is_kept(vocab):
    req = understand(
        gw_of(activity="run", start_text="Todtnau", duration_h_max=1, pace_min_per_km=6),
        vocab,
        "Laufrunde unter 1 Stunde, Tempo 6 min/km, Todtnau",
        None,
    )
    assert req.pace_min_per_km == 6 and req.discarded_model_numbers == 0


def test_minute_forms_of_part_hours_are_read():
    from hikeall.agent.understand import _user_numbers

    assert {15, 0.25} <= _user_numbers("eine viertel Stunde")
    assert {45, 0.75} <= _user_numbers("dreiviertel Stunde")
    assert {150, 2.5} <= _user_numbers("2h30")
    assert {45, 0.75} <= _user_numbers("3/4 Stunde")


# --- multi-day, events, groups (plan 3, task 6) ------------------------------------------

TODAY = date(2026, 10, 30)
STAGES = ["Pforzheim", "Forbach", "Hausach", "Hinterzarten", "Basel"]


class FakeTrails:
    """TrailLookup without a database: Hausach is on the trail, Todtnau is not."""

    def start_km(self, trail_id, lat, lon):
        return 61.0 if abs(lat - 48.2836) < 0.01 else None

    def stage_places(self, trail_id):
        return STAGES


def multi(vocab, message, previous=None, **kw):
    kw.setdefault("intent", "multiday")
    return understand(gw_of(**kw), vocab, message, previous, today=TODAY, trails=FakeTrails())


def test_three_days_westweg_from_hausach(vocab):
    req = multi(
        vocab,
        "Westweg in drei Tagen ab Hausach, am 12. Juni um 8:30 Uhr, 18 km pro Tag",
        trail_text="Westweg",
        start_text="Hausach",
        days=3,
        day_km=18,
        start_date="2027-06-12",
        start_time="08:30",
    )
    assert isinstance(req, HikeRequest)
    assert req.trail_id == "westweg-west"
    assert req.days == 3 and req.day_km == 18
    assert req.start_date == date(2027, 6, 12)  # relative to TODAY: next 12 June
    assert req.start_time == time(8, 30)
    assert req.start.tag_id == "place:hausach"
    assert "radius_km" not in kinds(req)
    text = echo(req, vocab)
    assert "3 Tage" in text and "12.06.2027" in text and "08:30" in text and "18 km" in text


def test_defaults_are_visible_in_echo(vocab):
    req = multi(
        vocab, "3 Tage Westweg ab Hausach", trail_text="Westweg", start_text="Hausach", days=3
    )
    assert isinstance(req, HikeRequest)
    assert req.day_km is None and req.start_time is None and req.start_date is None
    text = echo(req, vocab)
    assert "15 km (Standard)" in text and "09:00" in text


def test_bare_westweg_is_west_variant_and_echo_says_so(vocab):
    req = multi(
        vocab, "Westweg 3 Tage ab Hausach", trail_text="Westweg", start_text="Hausach", days=3
    )
    assert req.trail_id == "westweg-west" and req.trail_assumed
    assert "Westweg (Westvariante – Ostvariante möglich)" in echo(req, vocab)
    east = multi(
        vocab,
        "Westweg Ostvariante 3 Tage ab Hausach",
        trail_text="Westweg Ostvariante",
        start_text="Hausach",
        days=3,
    )
    assert east.trail_id == "westweg-ost" and not east.trail_assumed
    assert "Ostvariante" in echo(east, vocab) and "möglich" not in echo(east, vocab)


def test_start_off_trail_asks(vocab):
    res = multi(
        vocab, "Westweg 3 Tage ab Todtnau", trail_text="Westweg", start_text="Todtnau", days=3
    )
    assert isinstance(res, Clarify)
    assert res.question == "Todtnau liegt nicht am Westweg. Ab welchem Etappenort?"
    assert res.options == ["Hausach", "Hinterzarten"]  # only stage places that resolve


def test_missing_start_and_days_ask(vocab):
    res = multi(vocab, "Westweg 3 Tage", trail_text="Westweg", days=3)
    assert isinstance(res, Clarify)
    assert res.question == "Wo soll die Mehrtagestour starten?"
    assert res.options == ["Hausach", "Hinterzarten"]
    res = multi(vocab, "Westweg ab Hausach", trail_text="Westweg", start_text="Hausach")
    assert isinstance(res, Clarify) and res.question == "Wie viele Tage?"


def test_invented_or_invalid_days(vocab):
    res = multi(vocab, "Westweg ab Hausach", trail_text="Westweg", start_text="Hausach", days=4)
    assert isinstance(res, Clarify) and res.question == "Wie viele Tage?"  # R27
    req = multi(
        vocab, "Westweg 20 Tage ab Hausach", trail_text="Westweg", start_text="Hausach", days=20
    )
    assert isinstance(req, Clarify) or "Tage" in " ".join(req.unmatched)


def test_day_change_needs_previous_plan(vocab):
    res = multi(
        vocab, "Tag 3 kürzer", intent="change", day_change_day=3, day_change_direction="shorter"
    )
    assert isinstance(res, Clarify)
    day_hike = HikeRequest(intent="day_hike")
    res = multi(
        vocab,
        "Tag 3 kürzer",
        previous=day_hike,
        intent="change",
        day_change_day=3,
        day_change_direction="shorter",
    )
    assert isinstance(res, Clarify)  # no multi-day plan before


def test_day_change_on_multiday_plan(vocab):
    prev = multi(
        vocab, "Westweg 4 Tage ab Hausach", trail_text="Westweg", start_text="Hausach", days=4
    )
    req = multi(
        vocab,
        "Tag 3 kürzer",
        previous=prev,
        intent="change",
        day_change_day=3,
        day_change_direction="shorter",
    )
    assert isinstance(req, HikeRequest)
    assert req.intent == "change"
    assert req.day_change == DayChange(day=3, change="shorter")
    assert (req.trail_id, req.days, req.start.tag_id) == ("westweg-west", 4, "place:hausach")
    longer = multi(
        vocab,
        "Tag 5 länger",
        previous=prev,
        intent="change",
        day_change_day=5,
        day_change_direction="longer",
    )
    assert isinstance(longer, Clarify)  # plan has 4 days


def test_halbpension_unmatched(vocab):
    req = multi(
        vocab,
        "Westweg 3 Tage ab Hausach, Halbpension, mit Sauna",
        trail_text="Westweg",
        start_text="Hausach",
        days=3,
        wishes=[RawWish(text="Halbpension"), RawWish(text="mit Sauna")],
    )
    assert isinstance(req, HikeRequest)
    assert req.preferences == []
    assert set(req.unmatched) >= {"Halbpension", "mit Sauna"}


def test_events_intent(vocab):
    msg = "Halbmarathon im Juni bei Freiburg"
    req = understand(gw_of(intent="events", question=msg), vocab, msg, None, today=TODAY)
    assert isinstance(req, HikeRequest) and req.intent == "events"
    assert req.question == msg and req.start is None and req.constraints == []


def test_groups_intent(vocab):
    msg = "Lauftreff in Freiburg"
    req = understand(gw_of(intent="groups", question=msg), vocab, msg, None, today=TODAY)
    assert isinstance(req, HikeRequest) and req.intent == "groups"
    assert req.question == msg and req.start is None


def test_date_only_if_written(vocab):
    req = multi(
        vocab,
        "Westweg 3 Tage ab Hausach",
        trail_text="Westweg",
        start_text="Hausach",
        days=3,
        start_date="2027-06-12",
        start_time="09:00",
    )
    assert isinstance(req, HikeRequest)
    assert req.start_date is None and req.start_time is None
    assert req.discarded_model_numbers == 2


def test_relative_and_numeric_dates(vocab):
    def date_of(message):
        req = multi(vocab, message, trail_text="Westweg", start_text="Hausach", days=3)
        return req.start_date

    assert date_of("Westweg 3 Tage ab Hausach, morgen") == date(2026, 10, 31)
    assert date_of("Westweg 3 Tage ab Hausach am 5.11.") == date(2026, 11, 5)
    assert date_of("Westweg 3 Tage ab Hausach am 5.11.2026") == date(2026, 11, 5)
    assert date_of("Westweg 3 Tage ab Hausach am 3. Januar") == date(2027, 1, 3)
    assert date_of("Westweg 3 Tage ab Hausach am 30. Oktober") == date(2026, 10, 30)
    past = multi(
        vocab,
        "Westweg 3 Tage ab Hausach am 1.1.2025",
        trail_text="Westweg",
        start_text="Hausach",
        days=3,
    )
    assert past.start_date is None and any("Datum" in u for u in past.unmatched)
    bad = multi(
        vocab,
        "Westweg 3 Tage ab Hausach am 31. Februar",
        trail_text="Westweg",
        start_text="Hausach",
        days=3,
    )
    assert bad.start_date is None and any("Datum" in u for u in bad.unmatched)


def test_leap_day_dates(vocab):
    def date_of(message, today):
        req = understand(
            gw_of(intent="multiday", trail_text="Westweg", start_text="Hausach", days=3),
            vocab,
            message,
            None,
            today=today,
            trails=FakeTrails(),
        )
        return req

    msg = "Westweg 3 Tage ab Hausach am 29. Februar"
    assert date_of(msg, date(2028, 3, 5)).start_date == date(2032, 2, 29)  # no crash
    assert date_of(msg, date(2027, 1, 10)).start_date == date(2028, 2, 29)
    assert date_of("Westweg 3 Tage ab Hausach am 29.2.2027", TODAY).start_date is None


def test_pace_is_not_a_start_time(vocab):
    req = multi(
        vocab,
        "Westweg 3 Tage ab Hausach, Tempo um 5:30 min/km",
        trail_text="Westweg",
        start_text="Hausach",
        days=3,
        start_time="05:30",
    )
    assert req.start_time is None


def test_mehrtagestour_is_not_longer(vocab):
    prev = multi(
        vocab, "Westweg 4 Tage ab Hausach", trail_text="Westweg", start_text="Hausach", days=4
    )
    req = multi(
        vocab,
        "Mehrtagestour Tag 3",
        previous=prev,
        intent="change",
        day_change_day=3,
        day_change_direction="longer",
    )
    assert req.day_change is None and any("Änderung nicht erkannt" in u for u in req.unmatched)


def test_days_need_a_day_phrase(vocab):
    res = multi(
        vocab,
        "Westweg 20 km pro Tag ab Hausach",
        trail_text="Westweg",
        start_text="Hausach",
        days=20,
    )
    assert isinstance(res, Clarify) and res.question == "Wie viele Tage?"
    for msg in ("Westweg dreitägig ab Hausach", "Westweg drei Tage ab Hausach"):
        req = multi(vocab, msg, trail_text="Westweg", start_text="Hausach", days=3)
        assert req.days == 3


def test_rejected_day_change_is_reported(vocab):
    prev = multi(
        vocab, "Westweg 4 Tage ab Hausach", trail_text="Westweg", start_text="Hausach", days=4
    )
    req = multi(
        vocab,
        "mach es anders",
        previous=prev,
        intent="change",
        day_change_day=3,
        day_change_direction="shorter",
    )
    assert req.day_change is None and any("Änderung nicht erkannt" in u for u in req.unmatched)


def _kind_tag(tid, label, kind, pid, lat, lon):
    rule = NearPlace(place_id=pid, radius_km=15, lat=lat, lon=lon, kind=kind)
    return Tag(id=tid, label=label, category="place", rule=rule)


def test_city_wins_over_same_name_village(vocab):
    v = TagVocabulary(
        list(vocab.all())
        + [
            _kind_tag(
                "place:freiburg-im-breisgau", "Freiburg im Breisgau", "town", 1, 47.996, 7.849
            ),
            _kind_tag("place:freiburg", "Freiburg", "village", 2, 53.8, 9.2),  # far-away village
        ]
    )
    res = understand(gw_of(start_text="Freiburg"), v, "ab Freiburg", None)
    assert isinstance(res, HikeRequest)
    assert res.start.label == "Freiburg im Breisgau" and res.start.lat == 47.996


def test_exact_name_city_wins_over_same_name_village(vocab):
    v = TagVocabulary(
        list(vocab.all())
        + [
            _kind_tag("place:pforzheim", "Pforzheim", "town", 1, 48.89, 8.70),
            _kind_tag("place:pforzheim-n2", "Pforzheim", "village", 2, 50.0, 9.0),
        ]
    )
    res = understand(gw_of(start_text="Pforzheim"), v, "ab Pforzheim", None)
    assert isinstance(res, HikeRequest) and res.start.lat == 48.89


def test_lone_village_still_resolves(vocab):
    v = TagVocabulary(
        list(vocab.all()) + [_kind_tag("place:zzdorf", "Zzdorf", "village", 3, 47.9, 8.0)]
    )
    res = understand(gw_of(start_text="Zzdorf"), v, "ab Zzdorf", None)
    assert isinstance(res, HikeRequest) and res.start.label == "Zzdorf"


def test_ostweg_is_not_the_west_variant(vocab):
    req = multi(
        vocab, "3 Tage Ostweg ab Freudenstadt", trail_text="Ostweg", start_text="Hausach", days=3
    )
    assert isinstance(req, HikeRequest)
    assert req.trail_id == "ostweg" and req.trail_assumed is False
    east = multi(
        vocab,
        "3 Tage Westweg Ost ab Hausach",
        trail_text="Westweg Ost",
        start_text="Hausach",
        days=3,
    )
    assert east.trail_id == "westweg-ost"


def test_mittelweg_resolves(vocab):
    req = multi(
        vocab, "Mittelweg ab Pforzheim, 4 Tage", trail_text="Mittelweg", start_text="Hausach", days=4
    )
    assert isinstance(req, HikeRequest)
    assert req.trail_id == "mittelweg" and req.trail_assumed is False


def test_pforzheim_without_trail_asks_which_trail(vocab):
    res = multi(vocab, "3 Tage ab Pforzheim", start_text="Pforzheim", days=3)
    assert isinstance(res, Clarify)
    assert {"Mittelweg", "Ostweg", "Westweg"} <= set(res.options)


def test_unknown_trail_lists_all_four(vocab):
    res = multi(vocab, "3 Tage Kandelhöhenweg", trail_text="Kandelhöhenweg", days=3)
    assert isinstance(res, Clarify)
    assert set(res.options) == {"Westweg", "Westweg Ostvariante", "Mittelweg", "Ostweg"}


@pytest.mark.parametrize(
    "message",
    [
        "Rundweg, unter 200 Hm, über 15 km, Feldberg",
        "Laufrunde 8 km ab Todtnau",
        "Rundtour bei Todtnau",
        "Rundwanderung um Todtnau",
        "Rundkurs bei Todtnau",
        "Schleife bei Todtnau",
        "Streckenwanderung bei Todtnau",
        "Wanderung von Todtnau nach Feldberg",
    ],
)
def test_model_roundtrip_is_kept_when_the_message_states_it(vocab, message):
    for required in (True, False):
        req = understand(gw_of(start_text="Todtnau", roundtrip=required), vocab, message, None)
        assert kinds(req)["roundtrip"].required is required


def test_model_roundtrip_without_a_word_in_the_message_is_dropped(vocab):
    """Like R27 for numbers: the model set "kein Rundweg" although the user never said so
    (eval case u08); the condition is dropped and counted as a discarded model value."""
    message = "Wanderung im Umkreis von 3 km um Todtnau, über 20 km"
    gw = gw_of(start_text="Todtnau", roundtrip=False, length_km_min=20, radius_km_max=3)
    req = understand(gw, vocab, message, None)
    assert "roundtrip" not in kinds(req)
    assert req.discarded_model_numbers == 1
    # "rund 20 km" is an approximate value, not a roundtrip
    gw = gw_of(start_text="Todtnau", roundtrip=True, length_km_approx=20)
    assert "roundtrip" not in kinds(understand(gw, vocab, "rund 20 km ab Todtnau", None))
