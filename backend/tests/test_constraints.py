from hikeall.agent.constraints import (
    Candidate,
    check,
    contradiction,
    duration_h,
    format_deviation,
    preference_score,
    select,
)
from hikeall.agent.request import Constraint, HikeRequest, Preference, ResolvedStart


def cand(**kw) -> Candidate:
    base = {
        "trail_id": "t1",
        "name": "Tour",
        "length_km": 12.0,
        "ascent_m": 300,
        "descent_m": 300,
        "roundtrip": True,
        "distance_km": 2.0,
        "tags": set(),
    }
    base.update(kw)
    return Candidate(**base)


def req(
    *constraints, radius_max=None, prefs=(), activity="hike", pace=None, start_kind=None
) -> HikeRequest:
    cs = list(constraints)
    if radius_max is not None:
        cs.append(Constraint(kind="radius_km", max=radius_max))
    return HikeRequest(
        intent="day_hike",
        activity=activity,
        constraints=cs,
        preferences=list(prefs),
        pace_min_per_km=pace,
        start=ResolvedStart(kind=start_kind, tag_id="x", label="X") if start_kind else None,
    )


def test_unknown_value_never_satisfies():
    c = cand(ascent_m=None)
    [r] = check(c, [Constraint(kind="ascent_m", max=400)], "hike", None)
    assert r.ok is None
    assert r.deviation_rel == 1.0
    assert format_deviation(r) == "Höhenmeter unbekannt"


def test_check_ok_and_deviation():
    c = cand(ascent_m=340, length_km=18)
    rs = check(
        c,
        [
            Constraint(kind="ascent_m", max=200),
            Constraint(kind="length_km", min=10, max=20),
            Constraint(kind="roundtrip", required=True),
        ],
        "hike",
        None,
    )
    assert [r.ok for r in rs] == [False, True, True]
    assert rs[0].deviation_rel == 0.7
    assert format_deviation(rs[0]) == "340 Hm statt höchstens 200"


def test_roundtrip_violation():
    [r] = check(cand(roundtrip=False), [Constraint(kind="roundtrip", required=True)], "hike", None)
    assert r.ok is False and r.deviation_rel == 1.0
    assert format_deviation(r) == "kein Rundweg"


def test_fallback_has_exactly_one_violation_each():
    cands = [
        cand(trail_id="a", ascent_m=340),
        cand(trail_id="b", ascent_m=500),
        cand(trail_id="c", length_km=30.0),
        cand(trail_id="d", length_km=30.0, ascent_m=900),  # two violations
    ]
    r = req(
        Constraint(kind="ascent_m", max=200),
        Constraint(kind="length_km", max=20),
    )
    # every candidate violates ascent (300 > 200) except none; make ascent ok for c
    cands[2] = cand(trail_id="c", length_km=30.0, ascent_m=100)
    sel = select(cands, r)
    assert not sel.matches and sel.reason.startswith("Keine Tour erfüllt alle Wünsche, weil")
    assert sel.fallbacks
    for f in sel.fallbacks:
        assert sum(1 for x in f.results if x.ok is not True) == 1
    assert len({f.violated.kind for f in sel.fallbacks}) == len(sel.fallbacks)
    assert "d" not in {f.candidate.trail_id for f in sel.fallbacks}


def test_fallback_sorted_by_smallest_deviation():
    cands = [
        cand(trail_id="a", ascent_m=500, length_km=10),  # ascent dev 1.5 (max 200)
        cand(trail_id="b", ascent_m=100, length_km=22),  # length dev 0.1
        cand(trail_id="c", ascent_m=300, length_km=10),  # ascent dev 0.5
    ]
    sel = select(
        cands,
        req(Constraint(kind="ascent_m", max=200), Constraint(kind="length_km", max=20)),
    )
    assert [f.candidate.trail_id for f in sel.fallbacks] == ["b", "c"]
    devs = [f.violated.deviation_rel for f in sel.fallbacks]
    assert devs == sorted(devs)


def test_matches_capped_at_5_and_ordered_by_preferences():
    cands = [
        cand(trail_id=str(i), tags={"wald"} if i % 2 else set(), distance_km=float(i))
        for i in range(8)
    ]
    sel = select(cands, req(prefs=[Preference(tag_id="wald", mode="prefer", weight=3)]))
    assert len(sel.matches) == 5
    assert [m.candidate.trail_id for m in sel.matches] == ["1", "3", "5", "7", "0"]
    assert sel.fallbacks == [] and sel.reason is None


def test_avoid_lowers_score():
    p = [
        Preference(tag_id="wald", mode="avoid", weight=2),
        Preference(tag_id="see", mode="prefer", weight=4),
    ]
    m = preference_score(cand(tags={"wald", "see"}), p)
    assert m.score == 2 and m.met == ["see"] and m.avoided_hit == ["wald"] and m.missing == []
    m2 = preference_score(cand(tags=set()), p)
    assert m2.score == 0 and m2.missing == ["see"]


def test_contradictory_bounds():
    msg = contradiction([Constraint(kind="length_km", min=10, max=5)])
    assert msg == "Länge: mindestens 10 km und höchstens 5 km schließen sich aus"
    sel = select([cand()], req(Constraint(kind="length_km", min=10, max=5)))
    assert sel.contradiction == msg
    assert not sel.matches and not sel.fallbacks
    assert sel.reason.startswith("Keine Tour erfüllt alle Wünsche, weil")


def test_no_contradiction():
    assert contradiction([Constraint(kind="length_km", min=5, max=10)]) is None


def test_radius_fallback():
    sel = select([cand(distance_km=18)], req(radius_max=15, start_kind="place"))
    assert format_deviation(sel.fallbacks[0].violated) == "18 km entfernt statt höchstens 15"


def test_no_candidates_has_reason():
    sel = select([], req(radius_max=15, start_kind="place"))
    assert (
        sel.reason
        == "Keine Tour erfüllt alle Wünsche, weil im Umkreis von 15 km keine passende Tour liegt"
    )


def test_run_without_pace_has_no_duration():
    assert duration_h(cand(), "run", None) is None
    assert duration_h(cand(length_km=10), "run", 6.0) == 1.0


def test_hike_duration_din_and_missing():
    assert duration_h(cand(length_km=12, ascent_m=300, descent_m=300), "hike", None) == 3.8
    assert duration_h(cand(ascent_m=None), "hike", None) is None


def test_duration_constraint_unknown_for_run_without_pace():
    [r] = check(cand(), [Constraint(kind="duration_h", max=2)], "run", None)
    assert r.ok is None
    assert format_deviation(r) == "Dauer unbekannt"


def test_decimal_format():
    c = cand(length_km=12.5)
    [r] = check(c, [Constraint(kind="length_km", max=10)], "hike", None)
    assert format_deviation(r) == "12,5 km statt höchstens 10"


def test_unknown_fallback_reason_is_not_called_violation():
    sel = select([cand(ascent_m=None)], req(Constraint(kind="ascent_m", max=400)))
    assert "Höhenmeter unbekannt" in sel.reason
    assert "verletzt" not in sel.reason and "nicht erfüllt" not in sel.reason


def test_unknown_fallbacks_rank_after_real_violations():
    cands = [
        cand(trail_id="u", length_km=None, ascent_m=50),  # unknown length, dev 1.0
        cand(trail_id="r", ascent_m=900),  # real ascent dev 8.0
    ]
    sel = select(
        cands, req(Constraint(kind="ascent_m", max=100), Constraint(kind="length_km", max=20))
    )
    assert [f.candidate.trail_id for f in sel.fallbacks] == ["r", "u"]


def test_contradiction_across_constraints_of_same_kind():
    cs = [Constraint(kind="length_km", min=10), Constraint(kind="length_km", max=5)]
    assert contradiction(cs) == "Länge: mindestens 10 km und höchstens 5 km schließen sich aus"
    sel = select([cand()], req(*cs))
    assert sel.contradiction and not sel.fallbacks
    assert contradiction(
        [Constraint(kind="roundtrip", required=True), Constraint(kind="roundtrip", required=False)]
    )


def test_trail_id_tiebreak_is_deterministic():
    cands = [cand(trail_id=i) for i in ("c", "a", "b")]
    assert [m.candidate.trail_id for m in select(cands, req()).matches] == ["a", "b", "c"]
    fb = [cand(trail_id=i, ascent_m=500) for i in ("z", "m")]
    sel = select(fb, req(Constraint(kind="ascent_m", max=200)))
    assert [f.candidate.trail_id for f in sel.fallbacks] == ["m"]
    sel = select(fb[::-1], req(Constraint(kind="ascent_m", max=200)))
    assert [f.candidate.trail_id for f in sel.fallbacks] == ["m"]


def test_fallback_tie_prefers_higher_score():
    cands = [cand(trail_id="a", ascent_m=500), cand(trail_id="b", ascent_m=500, tags={"see"})]
    sel = select(
        cands,
        req(Constraint(kind="ascent_m", max=200), prefs=[Preference(tag_id="see", mode="prefer")]),
    )
    assert [f.candidate.trail_id for f in sel.fallbacks] == ["b"]


def test_small_violation_never_looks_equal_to_bound():
    [r] = check(cand(distance_km=15.04), [Constraint(kind="radius_km", max=15)], "hike", None)
    assert format_deviation(r) == "15,04 km entfernt statt höchstens 15"


def test_min_bound_deviation():
    [r] = check(cand(ascent_m=100), [Constraint(kind="ascent_m", min=400)], "hike", None)
    assert r.deviation_rel == 0.75
    assert format_deviation(r) == "100 Hm statt mindestens 400"


def test_nonpositive_pace_has_no_duration():
    assert duration_h(cand(), "run", 0.0) is None
    assert duration_h(cand(), "run", -5.0) is None


def test_empty_reason_area_and_place():
    area = select([], req(radius_max=15, start_kind="area"))
    assert (
        area.reason == "Keine Tour erfüllt alle Wünsche, weil im Gebiet keine passende Tour liegt"
    )
    assert "15" not in area.reason
    nostart = select([], req())
    assert nostart.reason.startswith("Keine Tour erfüllt alle Wünsche, weil")


def _bad(r) -> int:
    return sum(1 for x in r if x.ok is not True)


def test_rejected_holds_the_rest_sorted_and_capped():
    cs = (Constraint(kind="length_km", max=15), Constraint(kind="ascent_m", max=400))
    cands = [cand(trail_id=f"ok{i}", length_km=10.0, ascent_m=300) for i in range(2)]
    cands += [cand(trail_id=f"one{i:02d}", length_km=16.0 + i, ascent_m=300) for i in range(14)]
    cands += [cand(trail_id=f"two{i:02d}", length_km=16.0 + i, ascent_m=500) for i in range(14)]
    sel = select(cands, req(*cs))
    assert len(sel.matches) == 2
    assert len(sel.rejected) == 20
    bads = [_bad(s.results) for s in sel.rejected]
    assert bads == sorted(bads)
    assert len(sel.near_misses) == 1  # one00: 16 km vs 15 km
    assert bads[:13] == [1] * 13
    ids = [s.candidate.trail_id for s in sel.matches + sel.near_misses + sel.rejected]
    assert len(ids) == len(set(ids))


def test_rejected_includes_matches_beyond_max():
    cands = [cand(trail_id=f"t{i}", distance_km=float(i)) for i in range(7)]
    sel = select(cands, req(Constraint(kind="length_km", max=15)))
    assert len(sel.matches) == 5
    assert [s.candidate.trail_id for s in sel.rejected] == ["t5", "t6"]


def test_rejected_empty_on_contradiction():
    sel = select(
        [cand()], req(Constraint(kind="length_km", min=20), Constraint(kind="length_km", max=10))
    )
    assert sel.contradiction
    assert sel.rejected == []


def _near_req():
    return req(Constraint(kind="length_km", max=10))


def test_near_misses_fill_up_to_three():
    cands = [
        cand(trail_id="ok", length_km=9.0),
        cand(trail_id="n20", length_km=12.0),
        cand(trail_id="n05", length_km=10.5),
        cand(trail_id="n30", length_km=13.0),
    ]
    sel = select(cands, _near_req())
    assert [s.candidate.trail_id for s in sel.matches] == ["ok"]
    assert [s.candidate.trail_id for s in sel.near_misses] == ["n05", "n20"]
    assert "n30" in [s.candidate.trail_id for s in sel.rejected]
    assert all(s.candidate.trail_id not in ("n05", "n20") for s in sel.rejected)
    assert sel.near_misses[0].violated.kind == "length_km"


def test_near_miss_excludes_roundtrip_and_unknown():
    cands = [
        cand(trail_id="ok", length_km=9.0),
        cand(trail_id="rt", length_km=9.0, roundtrip=False),
        cand(trail_id="unk", length_km=None),
    ]
    sel = select(cands, req(Constraint(kind="length_km", max=10), Constraint(kind="roundtrip", required=True)))
    assert [s.candidate.trail_id for s in sel.matches] == ["ok"]
    assert sel.near_misses == []


def test_near_miss_needs_exactly_one_miss():
    cands = [cand(trail_id="ok", length_km=9.0), cand(trail_id="two", length_km=10.5, ascent_m=420)]
    sel = select(cands, req(Constraint(kind="length_km", max=10), Constraint(kind="ascent_m", max=400)))
    assert sel.near_misses == []


def test_no_near_misses_with_zero_or_three_matches():
    near = cand(trail_id="n", length_km=10.5)
    zero = select([near], _near_req())
    assert zero.matches == [] and zero.near_misses == []
    three = select([cand(trail_id=f"t{i}", length_km=9.0) for i in range(3)] + [near], _near_req())
    assert len(three.matches) == 3 and three.near_misses == []


def test_shown_trail_ids_include_near_misses():
    from hikeall.agent.tools import shown_trail_ids

    sel = select([cand(trail_id="ok", length_km=9.0), cand(trail_id="n", length_km=10.5)], _near_req())
    assert shown_trail_ids(sel) == ["ok", "n"]
