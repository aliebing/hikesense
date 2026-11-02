from test_constraints import cand, req

from hikeall.agent.constraints import MAX_MATCHES, format_deviation, select
from hikeall.agent.explain import candidate_rows
from hikeall.agent.request import Constraint


def test_rows_status_and_notes():
    cands = [
        cand(trail_id="a", length_km=22.3, ascent_m=300),
        cand(trail_id="b", length_km=16.0, ascent_m=300),
        cand(trail_id="c", length_km=22.3, ascent_m=900),
    ]
    sel = select(
        cands, req(Constraint(kind="length_km", max=15), Constraint(kind="ascent_m", max=400))
    )
    assert not sel.matches
    rows = candidate_rows(sel)
    assert rows[0]["status"] == "fallback"
    assert rows[0]["note"] == format_deviation(sel.fallbacks[0].violated)
    rej = next(r for r in rows if r["status"] == "rejected")
    assert "22,3 km statt" in rej["note"]
    assert rej["results"][0] == {
        "kind": "length_km",
        "ok": False,
        "actual": 22.3,
        "bound": "höchstens 15",
    }
    assert rows[0]["score"] == 0.0


def test_rows_note_for_surplus_match():
    cands = [cand(trail_id=f"t{i}", distance_km=float(i)) for i in range(7)]
    rows = candidate_rows(select(cands, req(Constraint(kind="length_km", max=15))))
    assert [r["status"] for r in rows] == ["shown"] * 5 + ["rejected"] * 2
    assert rows[0]["note"] is None
    assert rows[5]["note"] == f"nur die besten {MAX_MATCHES} gezeigt"
