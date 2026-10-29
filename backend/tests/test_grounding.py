import pytest

from hikeall.agent.grounding import Evidence, grounding_check, numbers_in_text


def ev(numbers=(), names=()) -> Evidence:
    return Evidence(numbers=list(numbers), names=list(names))


def test_unsupported_number_removed_and_counted():
    r = grounding_check("Die Tour hat 12,4 km und 999 Hm.", ev(numbers=["12.4 km"]))
    assert "999" not in r.text and r.unsupported == ["999 Hm"]


def test_rounded_number_is_supported():
    assert not grounding_check("etwa 12 km", ev(numbers=["12.4 km"])).unsupported


def test_more_precise_than_evidence_is_unsupported():
    # 12,45 is not 12,4 rounded to two places
    assert grounding_check("genau 12,45 km", ev(numbers=["12.4 km"])).unsupported == ["12,45 km"]


def test_hint_sentence_appended_with_count():
    r = grounding_check("Sie hat 5 km und 300 Hm und dauert 2 h.", ev(numbers=["5 km"]))
    assert r.unsupported == ["300 Hm", "2 h"]
    assert r.text.endswith(
        "Hinweis: 2 Angabe(n) ließ(en) sich nicht belegen und wurde(n) entfernt."
    )
    assert "? Hm" in r.text and "? h" in r.text


def test_no_hint_when_everything_supported():
    r = grounding_check("Die Runde hat 5 km.", ev(numbers=["5 km"]))
    assert r.text == "Die Runde hat 5 km." and r.unsupported == []


def test_numbers_without_unit_are_not_checked():
    r = grounding_check("Ich habe 3 Touren gefunden.", ev())
    assert r.unsupported == []


def test_german_thousands_separator_and_units():
    e = ev(numbers=["1200 m", "450 Hm"])
    assert not grounding_check("Er ist 1.200 m hoch, Anstieg 450 Höhenmeter.", e).unsupported


def test_unit_conversion_km_m_and_h_min():
    e = ev(numbers=["800 m", "2.5 h"])
    r = grounding_check("Die Hütte liegt 0,8 km entfernt; Gehzeit 150 min oder 2 h 30 min.", e)
    assert r.unsupported == []


def test_evidence_text_from_code_sentences():
    e = ev(numbers=["18 km entfernt statt höchstens 15 km"])
    assert not grounding_check("Sie liegt 18 km entfernt.", e).unsupported


def test_percent_and_minutes_patterns():
    assert numbers_in_text("Asphalt 40 %, Pause 15 min, 3 Std., 12,5km") == [
        "40 %",
        "15 min",
        "3 Std.",
        "12,5km",
    ]


def test_speed_is_not_a_length():
    assert numbers_in_text("mit 10 km/h") == []


# --- fix round 1 -------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["25 Kilometer", "500 Meter", "30 Prozent", "800 Höhenmeter"])
def test_german_long_unit_words_are_checked(text):
    r = grounding_check(f"Die Tour hat {text}.", ev(numbers=["12.4 km", "40 %", "450 Hm"]))
    assert r.unsupported == [text]


@pytest.mark.parametrize(
    "text", ["12 Kilometer", "12.400 Metern", "40 Prozent", "450 Höhenmetern", "3 Stunden"]
)
def test_german_long_unit_words_supported(text):
    e = ev(numbers=["12.4 km", "40 %", "450 Hm", "2.9 h"])
    assert grounding_check(f"Etwa {text}.", e).unsupported == []


@pytest.mark.parametrize(
    "text",
    ["2,9 h", "3 h", "knapp 3 Stunden", "2 h 54 min", "2:54 h", "174 min", "2 Std. 54 Minuten"],
)
def test_duration_supported_only_as_a_whole(text):
    assert grounding_check(f"Sie dauert {text}.", ev(numbers=["2.9 h"])).unsupported == []


@pytest.mark.parametrize("text", ["2 h", "54 min", "2 h 50 min", "2:50 h"])
def test_duration_parts_are_not_supported(text):
    r = grounding_check(f"Sie dauert {text}.", ev(numbers=["2.9 h"]))
    assert r.unsupported == [text]
    assert "2" not in r.text.split("\n")[0].replace("Sie dauert", "")


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("10 bis 15 km", ["10 km"]),
        ("10–15 km", ["10 km"]),
        ("10-15 km", ["10 km"]),
        ("zwischen 10 und 15 km", ["10 km"]),
        ("15 bis 20 km", ["20 km"]),
    ],
)
def test_both_numbers_of_a_range_are_checked(text, bad):
    r = grounding_check(f"Touren mit {text}.", ev(numbers=["15 km"]))
    assert r.unsupported == bad and "?" in r.text


def test_range_fully_supported():
    assert not grounding_check("10 bis 15 km", ev(numbers=["10 km", "15 km"])).unsupported


@pytest.mark.parametrize("text", ["450 m", "0,45 km", "450 Meter"])
def test_ascent_never_supports_length(text):
    assert grounding_check(f"Sie ist {text} lang.", ev(numbers=["450 Hm"])).unsupported == [text]


def test_length_never_supports_ascent():
    r = grounding_check("Sie hat 1200 Hm.", ev(numbers=["1.2 km", "1200 m"]))
    assert r.unsupported == ["1200 Hm"]
