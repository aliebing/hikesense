import pytest

from hikesense.agent.grounding import (
    NAME_HINT,
    Evidence,
    grounding_check,
    numbers_in_text,
    strip_unsat_claims,
)


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


# --- final wave: compounds, abbreviations, number words (I-2), tour names (I-4/R21) -------


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("Eine 15-km-Runde mit 900-Hm-Anstieg.", ["15-km", "900-Hm"]),
        ("Das sind ca.18 km.", ["18 km"]),
        ("Rund 3-Stunden-Tour.", ["3-Stunden"]),
        ("zwei Stunden und fünf Kilometer", ["zwei Stunden", "fünf Kilometer"]),
        ("Nach einer Stunde und elf Kilometern.", ["einer Stunde", "elf Kilometern"]),
        ("Anderthalb Stunden Gehzeit.", ["Anderthalb Stunden"]),
        ("Nur eine halbe Stunde.", ["eine halbe Stunde"]),
        ("zwei bis drei Stunden", ["zwei Stunden", "drei Stunden"]),
    ],
)
def test_compounds_abbreviations_and_number_words_are_checked(text, bad):
    r = grounding_check(text, ev(numbers=["12.4 km", "350 Hm", "4 h"]))
    assert r.unsupported == bad
    assert "?" in r.text


@pytest.mark.parametrize(
    "text",
    [
        "Eine 12-km-Runde mit 350-Hm-Anstieg.",
        "ca.12 km",
        "zwölf Kilometer und vier Stunden",
        "anderthalb Stunden",
        "eine halbe Stunde",
    ],
)
def test_compounds_and_number_words_supported_by_evidence(text):
    r = grounding_check(text, ev(numbers=["12 km", "350 Hm", "4 h", "1,5 h", "0,5 h"]))
    assert r.unsupported == []


def test_number_words_without_unit_are_not_checked():
    assert grounding_check("Zwei Touren und eine Einkehr.", ev()).unsupported == []


def test_decimal_dot_is_still_one_number():
    # "12.5 km" must not be read as "5 km" after an abbreviation dot
    assert grounding_check("12.5 km", ev(numbers=["12,5 km"])).unsupported == []


def test_unknown_tour_name_is_counted_not_removed():
    known = ["Feldberg-Runde", "Seebuck-Weg", "Wutachschlucht-Pfad"]
    r = grounding_check(
        "Die Feldberg-Runde passt; probier auch den Wutachschlucht-Pfad.",
        ev(names=["Feldberg-Runde"]),
        tour_names=known,
    )
    assert r.unsupported == []
    assert r.unsupported_names == ["Wutachschlucht-Pfad"]
    assert "Wutachschlucht-Pfad" in r.text  # hinted, never removed
    assert r.text.endswith(NAME_HINT.format(names="Wutachschlucht-Pfad"))


def test_tour_name_in_evidence_text_is_supported():
    r = grounding_check(
        "Der Westweg ist mit roter Raute markiert.",
        ev(numbers=["Der Westweg ist mit einer roten Raute markiert."]),
        tour_names=["Westweg"],
    )
    assert r.unsupported_names == []


def test_tour_name_needs_whole_word():
    r = grounding_check("Ein Panoramawegweiser.", ev(), tour_names=["Panoramaweg"])
    assert r.unsupported_names == []


def test_weather_units_and_clock_times_are_checked():
    ev = Evidence()
    ev.add(11.4, "°C")
    ev.add(85, "%")
    ev.add(7.5, "mm")
    ev.numbers.append("Ankunft 13:30 Uhr")
    g = grounding_check(
        "Bis 11 °C, 85 % Regen, 7,5 mm, an um 13:30 Uhr; nachts 2 Grad, 12 mm, an um 15 Uhr.", ev
    )
    assert g.unsupported == ["2 Grad", "12 mm", "15 Uhr"]
    assert "Bis 11 °C, 85 % Regen, 7,5 mm, an um 13:30 Uhr" in g.text


def test_minus_sign_is_part_of_the_number():
    ev = Evidence()
    ev.add(-3.0, "°C")
    ev.add(4.0, "°C")
    g = grounding_check("Tiefstwert 3 °C, höchstens 4 °C, nachts -3 °C, früh −3 °C.", ev)
    assert g.unsupported == ["3 °C"]
    assert g.text.startswith("Tiefstwert ? °C, höchstens 4 °C, nachts -3 °C, früh −3 °C.")
    assert grounding_check("Tiefstwert −3 °C", Evidence(numbers=["-3 °C"])).unsupported == []
    assert grounding_check("Tiefstwert -3 °C", Evidence(numbers=["3 °C"])).unsupported == ["-3 °C"]


def test_ranges_and_compounds_keep_working_with_signs():
    known = Evidence(numbers=["10 km", "14 km", "3 km"])
    assert grounding_check("10–14 km", known).unsupported == []
    assert grounding_check("10-14 km", known).unsupported == []
    assert grounding_check("10 - 14 km", known).unsupported == []
    assert grounding_check("eine 3-Tage-Tour über 3 km", known).unsupported == []
    assert grounding_check("-3 bis 4 °C", Evidence(numbers=["-3 °C", "4 °C"])).unsupported == []


# --- plan 3, task 13: the numbers the code shows the model must pass the check ------------------


@pytest.mark.parametrize(
    ("value", "unit"), [(4.35, "h"), (15.05, "km"), (-4.35, "°C"), (2.25, "h")]
)
def test_numbers_formatted_for_the_model_are_supported(value, unit):
    """Smoke case 8: the plan line said "Gehzeit 4,3 h" (float rounding of 4.35) while the
    evidence 4,35 h rounds half-up to 4,4 – the model's faithful copy was replaced by "?"."""
    from hikesense.agent.graph import _de

    ev = Evidence()
    ev.add(value, unit)
    assert grounding_check(f"Es sind {_de(value)} {unit}.", ev).unsupported == []


def test_unknown_tour_name_gets_a_hint():
    r = grounding_check(
        "Probier den Feldbergsteig, die Hochfirstrunde ist auch schön.",
        ev(names=["Hochfirstrunde"]),
        tour_names=["Feldbergsteig", "Hochfirstrunde"],
    )
    assert r.unsupported_names == ["Feldbergsteig"] and r.unsupported == []
    assert "Feldbergsteig" in r.text
    assert r.text.endswith(
        "Hinweis: Feldbergsteig kommt in den Suchergebnissen dieser Antwort nicht vor"
        " – bitte nicht als Vorschlag verstehen."
    )


def test_several_unknown_names_use_plural_hint():
    r = grounding_check("Feldbergsteig und Seeweg.", ev(), tour_names=["Feldbergsteig", "Seeweg"])
    assert r.text.endswith(
        "Hinweis: Feldbergsteig, Seeweg kommen in den Suchergebnissen"
        " dieser Antwort nicht vor – bitte nicht als Vorschlag verstehen."
    )


def test_known_names_get_no_hint():
    r = grounding_check(
        "Die Hochfirstrunde.", ev(names=["Hochfirstrunde"]), tour_names=["Hochfirstrunde"]
    )
    assert r.unsupported_names == [] and r.text == "Die Hochfirstrunde."


def test_number_hint_comes_before_name_hint():
    r = grounding_check("Feldbergsteig, 999 Hm.", ev(), tour_names=["Feldbergsteig"])
    assert r.text.index("Angabe(n)") < r.text.index("Feldbergsteig kommt")


@pytest.mark.parametrize(
    "text, want",
    [
        (
            "Keine Tour erfüllt alle Wünsche, aber hier sind Vorschläge:\n\n1. Säbelthomaweg",
            "1. Säbelthomaweg",
        ),
        (
            "Keine Tour erfüllt alle Wünsche, weil es regnet. Der Jägersteig passt.",
            "Der Jägersteig passt.",
        ),
        ("Hallo! Leider erfüllt keine der Touren alle deine Bedingungen. Gut.", "Hallo! Gut."),
        ("Keine dieser Wanderungen erfüllt sämtliche Anforderungen.", ""),
        # an abbreviation does not end the sentence: no fragment of the claim is left
        (
            "Keine Tour erfüllt alle Wünsche, z. B. die Länge. Der Jägersteig passt.",
            "Der Jägersteig passt.",
        ),
        # up to two words between der/dieser and the verb
        (
            "Keine der drei Touren erfüllt alle Wünsche. Der Jägersteig passt.",
            "Der Jägersteig passt.",
        ),
        # list numbering is not a sentence end: the item goes as a whole, the line break stays
        (
            "1. Tour A\n2. Keine Tour erfüllt alle Wünsche\n3. Tour B",
            "1. Tour A\n3. Tour B",
        ),
    ],
)
def test_unsat_claim_removed_and_counted(text, want):
    assert strip_unsat_claims(text) == (want, 1)


@pytest.mark.parametrize(
    "text",
    [
        "Der Jägersteig erfüllt alle Wünsche.",
        "Die Tour erfüllt nicht alle Vorlieben: Aussicht fehlt.",
        "Keine Tour ist kürzer als 10 km.",
        "Der Plan erfüllt alle Wünsche, es gibt keine Lücke.",
        "Alle drei Touren erfüllen alle deine Wünsche, keine Abweichung.",
        "Tag 2 ist länger, weil es keine Unterkunft gibt, und erfüllt damit nicht alle Vorgaben.",
        "Ca. 3 km bis zur Hütte, z. B. über den Gipfel. Keine Tour ist zu steil.",
    ],
)
def test_other_sentences_stay(text):
    assert strip_unsat_claims(text) == (text, 0)


# --- English answers (lang="en") ----------------------------------------------------------


def en(answer, numbers=(), names=()):
    return grounding_check(answer, ev(numbers, names), lang="en")


def test_en_point_decimal_and_thousands_comma_are_supported():
    r = en("It is 12.3 km long with 1,200 m of ascent.", ["12.3 km", "1200 Hm"])
    assert r.unsupported == [] and r.text == "It is 12.3 km long with 1,200 m of ascent."


def test_en_unsupported_number_becomes_question_mark_with_english_hint():
    r = en("The tour is 15.0 km long.", ["12.3 km"])
    assert r.unsupported == ["15.0 km"]
    assert "?" in r.text and "15.0" not in r.text
    assert r.text.endswith("Note: 1 figure(s) could not be verified and were removed.")


def test_en_comma_thousands_is_not_a_decimal():
    # "1,500" is 1500, not 1.5: 1.5 km of evidence must not support it
    assert en("The stop is 1,500 m away.", ["1.5 m"]).unsupported == ["1,500 m"]
    assert en("The stop is 1,500 m away.", ["1500 m"]).unsupported == []


def test_en_ascent_data_in_metres_matches_german_evidence_unit():
    e = ["ascent 540 m", "descent 560 m", "12.3 km"]
    assert en("540 m of ascent and 560 m of descent over 12.3 km", e).unsupported == []


def test_en_ascent_context_does_not_match_a_length():
    r = en("Total ascent of 800 m.", ["800 km"])
    assert r.unsupported == ["800 m"]


def test_en_unit_words():
    e = ["12.3 km", "3.5 h", "2 mm", "40 %", "18 °C", "800 m"]
    answer = (
        "12.3 kilometres, 3.5 hours, 2 millimetres of rain, 40 percent chance, 18 degrees, "
        "800 metres away"
    )
    assert en(answer, e).unsupported == []
    assert en("about 3 hrs", ["3 h"]).unsupported == []
    assert en("about 4 hours", ["3 h"]).unsupported == ["4 hours"]


def test_en_duration_forms():
    e = ["2.9 h"]
    assert en("2 h 54 min", e).unsupported == []
    assert en("2 hours and 54 minutes", e).unsupported == []
    assert en("2:54 h", e).unsupported == []
    assert en("2 hours and 10 minutes", e).unsupported == ["2 hours and 10 minutes"]


def test_en_ranges_and_number_words():
    e = ["10 km", "15 km"]
    assert en("between 10 and 15 km", e).unsupported == []
    assert en("10 to 15 km", e).unsupported == []
    assert en("10 to 20 km", e).unsupported == ["20 km"]
    assert en("about ten kilometres", e).unsupported == []
    assert en("about twelve kilometres", e).unsupported == ["twelve kilometres"]
    assert en("half an hour", ["30 min"]).unsupported == []


def test_en_clock_times():
    e = ["09:30"]
    assert en("Start at 09:30.", e).unsupported == []
    assert en("Start at 9:30 am.", e).unsupported == []
    assert en("Start at 10:00.", e).unsupported == ["10:00"]
    # a pace is not a clock time
    assert en("A pace of 5:30 min/km.", []).unsupported == []


def test_en_speed_is_no_length_and_german_evidence_format_is_read():
    assert en("Walk at 5 km/h.", []).unsupported == []
    assert en("It is 12.4 km.", ["12,4 km"]).unsupported == []  # German-format passage text
    assert en("It is 1,200 m high.", ["1.200 m"]).unsupported == []


def test_german_grounding_ignores_english_rules():
    # German: "1,500" is 1.5 and "1.500" is 1500
    assert grounding_check("1,5 km", ev(["1.5 km"])).unsupported == []
    assert grounding_check("1.500 m", ev(["1500 m"])).unsupported == []
    assert grounding_check("1,200 m", ev(["1200 m"])).unsupported == ["1,200 m"]


def test_en_name_hint_is_english():
    r = grounding_check("Try Seeweg.", ev(), ["Seeweg"], lang="en")
    assert r.unsupported_names == ["Seeweg"]
    assert r.text.endswith(
        "Note: Seeweg does not appear in this answer's search results"
        " – please do not take it as a suggestion."
    )
    r = grounding_check("Try Seeweg and Feldweg.", ev(), ["Seeweg", "Feldweg"], lang="en")
    assert "do not appear in this answer's search results" in r.text


def test_numbers_in_text_en():
    assert numbers_in_text("11.6 km and 1,200 m", "en") == ["11.6 km", "1,200 m"]


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("No tour meets all your wishes. Try the Seeweg.", 1),
        ("None of the tours meets all your conditions.", 1),
        ("Unfortunately none of these tours fulfils all of your requirements.", 1),
        ("There is no tour that meets all your criteria.", 1),
        ("Hello. No tour can meet all your wishes, sorry.", 1),
        ("This tour meets all your wishes.", 0),
        ("No tour is longer than 12.5 km. It meets all your wishes.", 0),
        ("I found 3 tours, e.g. the Seeweg.", 0),
    ],
)
def test_en_unsat_claim_removed_and_counted(text, want):
    out, n = strip_unsat_claims(text, "en")
    assert n == want
    if want:
        assert "meet" not in out.lower() and "fulfil" not in out.lower()


def test_en_unsat_strip_keeps_decimal_sentences_whole():
    out, n = strip_unsat_claims("The Seeweg is 11.6 km long. No tour meets all your wishes.", "en")
    assert n == 1 and out == "The Seeweg is 11.6 km long."


def test_de_unsat_strip_ignores_english():
    assert strip_unsat_claims("No tour meets all your wishes.")[1] == 0


@pytest.mark.parametrize(
    ("answer", "shown"),
    [
        ("It is 1,5 km long.", ["1,5 km"]),
        ("It is 12,5 km long.", ["12,5 km"]),
        ("It takes about an hour.", ["an hour"]),
        ("Only a kilometre away.", ["a kilometre"]),
        ("Start at 4 pm.", ["4"]),
        ("Start at 8 am.", ["8"]),
        ("Start at 9 o'clock.", ["9"]),
        ("It is 7 miles long.", ["7 miles"]),
        ("A climb of 500 feet.", ["500 feet"]),
        ("It takes three and a half hours.", ["three and a half hours"]),
        ("It takes 3 and a half hours.", ["3 and a half hours"]),
    ],
)
def test_en_invented_forms_are_caught(answer, shown):
    r = en(answer, ["540 Hm", "2.5 h", "12 km"])
    assert [x.split()[0] for x in r.unsupported] == [x.split()[0] for x in shown]
    assert "?" in r.text


def test_en_supported_forms_stay():
    e = ["540 Hm", "2.5 h", "12 km", "16:00", "08:00", "09:00", "1 h", "1 km"]
    for text in (
        "Start at 4 pm, 8 am or 9 o'clock.",
        "It takes two and a half hours.",
        "About an hour, a kilometre.",
        "12,0 km",
        "A 12 km walk",
        "I am 5 m",
    ):
        r = en(text, e + ["5 m"])
        assert r.unsupported == [], (text, r.unsupported)


def test_en_unsat_subject_needs_a_tour_noun():
    assert strip_unsat_claims("No doubt it meets all your wishes.", "en")[1] == 0
    assert strip_unsat_claims("No doubt the Seeweg meets all your wishes.", "en")[1] == 0
    assert strip_unsat_claims("No matching tour meets all your wishes.", "en")[1] == 1
    assert strip_unsat_claims("None of the three tours meets all your wishes.", "en")[1] == 1


# --- final fix wave: dotted am/pm, number words above twelve, bare "m" as length -----------


def test_en_dotted_pm_is_read_as_clock_time():
    assert en("Back at 1:25 p.m.", ["13:25 Uhr"]).unsupported == []
    assert en("Back at 1:25 p.m.", []).unsupported == ["1:25 p.m."]
    assert en("Start at 3 p.m. sharp.", []).unsupported != []
    assert en("Start at 9 a.m.", ["9:00 Uhr"]).unsupported == []


@pytest.mark.parametrize(
    "text,ev_text",
    [
        ("about twenty minutes", "20 min"),
        ("fifteen km", "15 km"),
        ("thirteen km", "13 km"),
        ("twenty-five minutes", "25 min"),
        ("thirty minutes", "30 min"),
        ("sixty minutes", "60 min"),
    ],
)
def test_en_number_words_above_twelve(text, ev_text):
    assert en(text, []).unsupported != []
    assert en(text, [ev_text]).unsupported == []


def test_en_number_word_compound_value_must_match():
    assert en("twenty-five minutes", ["20 min"]).unsupported != []


def test_en_bare_m_before_length_words_is_not_ascent():
    assert en("The hut is 540 m long.", ["540 Hm"]).unsupported != []
    assert en("The hut is 540 m away.", ["540 Hm"]).unsupported != []
    assert en("The hut is 540 m long.", ["540 m"]).unsupported == []
    assert en("an ascent of 540 m", ["540 Hm"]).unsupported == []
    assert en("540 m", ["540 Hm"]).unsupported == []
