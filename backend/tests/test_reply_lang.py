import pytest

from hikesense.agent.reply_lang import detect_lang, reply_lang


@pytest.mark.parametrize(
    "msg",
    [
        "Rundweg 10–14 km um Hinterzarten, unter 400 Hm",
        "3 Tage Westweg ab Hausach",
        "Wie ist der Westweg markiert?",
        "mach Tag 3 kürzer",
        "Rundwanderung bei Überlingen mit Einkehr",
        "zweitägigen Westweg ab Hausach",
        "Feldberg (Gemeinde)",
    ],
)
def test_german_messages(msg):
    assert detect_lang(msg) == "de"


@pytest.mark.parametrize(
    "msg",
    [
        "3 days on the Westweg from Hausach",
        "Circular hike near Meersburg, at most 12 km",
        "Hike near Hinterzarten, 10 to 14 km, under 400 m of ascent",
        "3 days on the Pfälzer Weinsteig from Annweiler am Trifels, about 15 km a day",
        "How is the Westweg waymarked?",
        "Round walk near Überlingen with a place to eat",  # umlauts in a place name do not count
        "make day 3 shorter",
        "Feldberg (peak)",
    ],
)
def test_english_messages(msg):
    assert detect_lang(msg) == "en"


@pytest.mark.parametrize("msg", ["Hausach", "Westweg", "Titisee 10 km", "", "Feldberg"])
def test_place_names_and_numbers_decide_nothing(msg):
    assert detect_lang(msg) is None


def test_unclear_message_keeps_the_conversation_language_then_the_page_language():
    assert reply_lang("Hausach", previous="en", page="de") == "en"
    assert reply_lang("Hausach", previous=None, page="de") == "de"
    assert reply_lang("3 Tage Westweg ab Hausach", previous="en", page="en") == "de"
    assert reply_lang("3 days on the Westweg", previous="de", page="de") == "en"
