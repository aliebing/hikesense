"""Fixed sentences of the agent in both reply languages (system prompts stay in prompts.py)."""

from __future__ import annotations

from dataclasses import dataclass

from hikesense.numfmt import Lang
from hikesense.regions import REGION_NAMES, REGION_PHRASE

REGION_NAMES_EN = "Black Forest, Lake Constance and Palatinate Forest"
REGION_PHRASE_EN = (
    "in the Black Forest, at Lake Constance (including the Swiss and Austrian shores) "
    "and in the Palatinate Forest"
)

_GROUP_AUTO_DE = "automatisch geprüft (Seite und Name abgerufen), noch nicht von Hand bestätigt"
_GROUP_HAND_DE = "von Hand geprüft"
_GROUP_AUTO_EN = "checked automatically (page and name fetched), not yet confirmed by hand"
_GROUP_HAND_EN = "checked by hand"


@dataclass(frozen=True)
class Texts:
    no_plan_at_start: str
    no_plan_to_change: str
    day_unknown: str
    events_note: str
    events_found: str
    events_none: str
    events_search_down: str
    events_skipped: str
    groups_found: str
    group_auto: str
    group_hand: str
    groups_check_all: str
    groups_check_mixed: str
    groups_stale: str
    groups_none: str
    groups_no_coords: str
    other_reply: str
    leak_reply: str
    clarify_start: str
    error_unavailable: str
    error_budget: str
    tool_limit: str
    tool_error: str
    tool_unknown: str
    trail_not_found: str
    claim_only_tours: str
    no_tours_hint: str
    contradiction_hint: str
    no_source_reply: str
    react_tours: str
    injection_reply: str
    rate_limit_reply: str
    # words the code puts into the placeholders of the events and groups sentences
    word_run: str
    word_runs: str
    word_page: str
    word_pages: str
    word_group: str
    word_groups: str
    word_is: str
    word_are: str
    kind_lauftreff: str
    kind_alpenverein: str
    kind_wanderverein: str
    # weather day finder (code-written sentences, never from the model)
    wish_fine: str
    wish_dry: str
    wish_snow: str
    weather_unavailable: str
    weather_found: str
    weather_none: str
    weather_day_fits: str
    weather_day_misses: str
    weather_day_unknown: str
    weather_others: str
    weather_no_others: str
    weather_data: str
    weather_fact_none: str  # facts for the model when the finder has no fitting day
    weather_fact_misses: str
    weather_fact_down: str
    weather_fact_unknown: str
    weather_label: str  # the model data's forecast line starts with it
    weather_nopoint: str  # code sentence and fact: no usable forecast point
    # multi-day weather window (code-written; {starts} are dates, {days} the plan's day numbers)
    weather_window_found: str
    weather_window_none: str
    weather_window_all: str
    weather_window_part: str


DE = Texts(
    no_plan_at_start=(
        "Ab {start} kann ich auf dem {trail} keinen Mehrtagesplan erstellen – der Ort liegt am "
        "Wegende oder nicht am Weg. Nenne bitte einen Etappenort davor."
    ),
    no_plan_to_change=(
        "Es gibt in diesem Gespräch noch keinen Mehrtagesplan, den ich ändern kann. "
        "Nenne bitte Fernweg, Startort und Anzahl der Tage."
    ),
    day_unknown="Der Plan hat {n} Tag(e) – einen Tag {day} gibt es darin nicht.",
    events_note="Angaben ohne Gewähr – bitte beim Veranstalter prüfen. Gesucht am {date}.",
    events_found=(
        "{n} {noun} gefunden ({pages} {page_noun} gelesen). Jede Angabe steht wörtlich auf der "
        "verlinkten Seite; was dort nicht steht, heißt „nicht angegeben“."
    ),
    events_none=(
        "Ich habe keinen kommenden Lauf mit einem auf der Veranstalterseite belegten Datum "
        "gefunden ({pages} {page_noun} gelesen). Hier sind Laufkalender zum Selbstsuchen."
    ),
    events_search_down=(
        "Die Websuche ist gerade nicht erreichbar. Hier sind Laufkalender zum Selbstsuchen."
    ),
    events_skipped=" {n} {page_noun} übersprungen ({reasons}).",
    groups_found=(
        "{n} {noun} im Umkreis von {radius} km um {place}, nach Abstand sortiert – {note}. "
        "{check} Die Liste ist nicht vollständig; Treffzeiten und Ansprechpersonen "
        "stehen auf den Seiten der Gruppen."
    ),
    group_auto=_GROUP_AUTO_DE,
    group_hand=_GROUP_HAND_DE,
    groups_check_all="Alle Einträge: {label}.",
    groups_check_mixed="Davon {hand} " + _GROUP_HAND_DE + ", {auto} " + _GROUP_AUTO_DE + ".",
    groups_stale=" {n} mit Prüfdatum älter als 180 Tage {verb} als „veraltet“ markiert.",
    groups_none=(
        "In meiner Liste gibt es keine Gruppe{kind} im Umkreis von {radius} km um {place}. "
        "Die Liste ist nicht vollständig."
    ),
    groups_no_coords="Für {place} kenne ich keine Koordinate – nenne bitte einen Ort in der Nähe.",
    other_reply=(
        "Dabei kann ich leider nicht helfen – ich plane Wanderungen und Laufrunden "
        f"{REGION_PHRASE} und beantworte Fragen dazu. Wohin soll es gehen?"
    ),
    leak_reply="Dazu kann ich nichts sagen.",
    clarify_start=(
        f"Wo soll die Tour starten? Nenne bitte einen Ort oder eine Gegend ({REGION_NAMES})."
    ),
    error_unavailable="Der Planungs-Assistent ist gerade nicht erreichbar. Bitte später noch einmal.",
    error_budget="Diese Anfrage wurde zu aufwendig – bitte enger fassen.",
    tool_limit=(
        "Werkzeug-Limit erreicht – dieser Aufruf wurde nicht ausgeführt. "
        "Bitte antworte jetzt mit den vorhandenen Angaben."
    ),
    tool_error=(
        "Fehler bei {name}: Das Werkzeug konnte mit diesen Angaben nicht ausgeführt werden "
        "({kind}). Antworte ohne dieses Ergebnis oder versuche andere Angaben."
    ),
    tool_unknown="Fehler: Das Werkzeug {name} gibt es nicht.",
    trail_not_found="Keine Tour mit dieser ID gefunden.",
    claim_only_tours="Hier sind die passenden Touren.",
    no_tours_hint=(
        "Versuch es mit einem größeren Umkreis, einem anderen Startort oder weniger Bedingungen."
    ),
    contradiction_hint="Bitte passe eine der Angaben an.",
    no_source_reply=(
        "Dazu habe ich in meinen Quellen nichts gefunden – und ohne Quelle antworte ich lieber "
        "nicht. Frag gern anders oder nach einer Tour."
    ),
    react_tours=(
        "Zuletzt vorgeschlagene Touren in diesem Gespräch (trail_id: Name) – nutze die trail_id "
        "für get_trail_details und find_accommodation:"
    ),
    injection_reply=(
        "Dabei kann ich nicht helfen. Frag mich gern nach Wanderungen oder Laufrunden "
        f"({REGION_NAMES})."
    ),
    rate_limit_reply="Zu viele Anfragen – bitte in {s} Sekunden noch einmal.",
    word_run="Lauf",
    word_runs="Läufe",
    word_page="Seite",
    word_pages="Seiten",
    word_group="Gruppe",
    word_groups="Gruppen",
    word_is="ist",
    word_are="sind",
    kind_lauftreff=" (Lauftreff)",
    kind_alpenverein=" (Alpenverein)",
    kind_wanderverein=" (Wanderverein)",
    wish_fine="schönes Wetter",
    wish_dry="trocken",
    wish_snow="Schnee",
    weather_unavailable="Wetter gerade nicht abrufbar.",
    weather_found="Passende Tage für ‚{wish}‘ bei {place}: {days}.",
    weather_none=(
        "In den nächsten 14 Tagen passt kein Tag zu ‚{wish}‘ bei {place}; am ehesten: {days}."
    ),
    weather_day_fits="{day} passt zu ‚{wish}‘ bei {place}: {detail}.",
    weather_day_misses="{day} passt nicht zu ‚{wish}‘ bei {place}: {detail}.",
    weather_day_unknown=(
        "Ob {day} zu ‚{wish}‘ bei {place} passt, lässt sich nicht sagen (Werte fehlen): {detail}."
    ),
    weather_others=" Weitere passende Tage: {days}.",
    weather_no_others=" In den nächsten 14 Tagen passt kein weiterer Tag.",
    weather_data="Wettervorhersage für „{wish}“ bei {place}, passende Tage: {days}",
    weather_fact_none="Wettervorhersage für „{wish}“ bei {place}: In den nächsten 14 Tagen passt kein Tag.",
    weather_fact_misses="Wettervorhersage für „{wish}“ bei {place}: {day} passt nicht zu „{wish}“.",
    weather_fact_down="Wettervorhersage nicht abrufbar.",
    weather_label="Wettervorhersage",
    weather_fact_unknown="Wettervorhersage für „{wish}“ bei {place}: Ob {day} passt, lässt sich nicht sagen (Werte fehlen).",
    weather_nopoint="Wetter für {place} nicht bestimmbar.",
    weather_window_found=(
        "Passende Starttage für ‚{wish}‘ bei den Tageszielen ({n} Tage): {starts}; "
        "der Plan beginnt am {first}"
    ),
    weather_window_none=(
        "In den nächsten 14 Tagen passt kein Starttag für alle {n} Tage zu ‚{wish}‘ bei den "
        "Tageszielen; höchstens {fits} von {n} Tagen passen, ab {start}"
    ),
    weather_window_all="Alle {n} Tage passen zu ‚{wish}‘ bei den Tageszielen.",
    weather_window_part=(
        "{fits} von {n} Tagen passen zu ‚{wish}‘ bei den Tageszielen; nicht bestätigt: {days}."
    ),
)

EN = Texts(
    no_plan_at_start=(
        "I can't build a multi-day plan on the {trail} from {start} – the place is at the end "
        "of the trail or not on it. Please name a stage town before it."
    ),
    no_plan_to_change=(
        "There is no multi-day plan in this conversation yet that I could change. "
        "Please name the long-distance trail, the start and the number of days."
    ),
    day_unknown="The plan has {n} day(s) – there is no day {day} in it.",
    events_note="No guarantee for these details – please check with the organiser. Searched on {date}.",
    events_found=(
        "Found {n} {noun} ({pages} {page_noun} read). Every detail is quoted verbatim from the "
        "linked page; anything not stated there reads “not stated”."
    ),
    events_none=(
        "I found no upcoming run with a date backed by the organiser's page "
        "({pages} {page_noun} read). Here are race calendars to search yourself."
    ),
    events_search_down=(
        "The web search is not available right now. Here are race calendars to search yourself."
    ),
    events_skipped=" {n} {page_noun} skipped ({reasons}).",
    groups_found=(
        "{n} {noun} within {radius} km of {place}, sorted by distance – {note}. "
        "{check} The list is not complete; meeting times and contact people "
        "are on the groups' own pages."
    ),
    group_auto=_GROUP_AUTO_EN,
    group_hand=_GROUP_HAND_EN,
    groups_check_all="All entries: {label}.",
    groups_check_mixed="Of these, {hand} " + _GROUP_HAND_EN + ", {auto} " + _GROUP_AUTO_EN + ".",
    groups_stale=" {n} with a check date older than 180 days {verb} marked as “outdated”.",
    groups_none=(
        "My list has no group{kind} within {radius} km of {place}. The list is not complete."
    ),
    groups_no_coords=("I don't know coordinates for {place} – please name a place nearby."),
    other_reply=(
        "I'm afraid I can't help with that – I plan walks and round walks "
        f"{REGION_PHRASE_EN} and answer questions about them. Where would you like to go?"
    ),
    leak_reply="I can't say anything about that.",
    clarify_start=(
        f"Where should the tour start? Please name a place or an area ({REGION_NAMES_EN})."
    ),
    error_unavailable="The planning assistant is not available right now. Please try again later.",
    error_budget="This request became too costly – please narrow it down.",
    tool_limit=(
        "Tool limit reached – this call was not executed. "
        "Please answer now with the information you have."
    ),
    tool_error=(
        "Error in {name}: the tool could not be run with these inputs ({kind}). "
        "Answer without this result or try different inputs."
    ),
    tool_unknown="Error: there is no tool {name}.",
    trail_not_found="No tour found with this ID.",
    claim_only_tours="Here are the matching tours.",
    no_tours_hint="Try a wider radius, a different start or fewer conditions.",
    contradiction_hint="Please adjust one of the details.",
    no_source_reply=(
        "I found nothing about that in my sources – and without a source I'd rather not "
        "answer. Feel free to ask differently or ask for a tour."
    ),
    react_tours=(
        "Tours suggested most recently in this conversation (trail_id: name) – use the "
        "trail_id for get_trail_details and find_accommodation:"
    ),
    injection_reply=(
        "I can't help with that. Feel free to ask me about walks or round runs "
        f"({REGION_NAMES_EN})."
    ),
    rate_limit_reply="Too many requests – please try again in {s} seconds.",
    word_run="run",
    word_runs="runs",
    word_page="page",
    word_pages="pages",
    word_group="group",
    word_groups="groups",
    word_is="is",
    word_are="are",
    kind_lauftreff=" (running club)",
    kind_alpenverein=" (Alpine Club)",
    kind_wanderverein=" (hiking club)",
    wish_fine="fine weather",
    wish_dry="dry",
    wish_snow="snow",
    weather_unavailable="Weather currently unavailable.",
    weather_found="Days that fit ‘{wish}’ near {place}: {days}.",
    weather_none=(
        "No day in the next 14 days fits ‘{wish}’ near {place}; closest: {days}."
    ),
    weather_day_fits="{day} fits ‘{wish}’ near {place}: {detail}.",
    weather_day_misses="{day} does not fit ‘{wish}’ near {place}: {detail}.",
    weather_day_unknown=(
        "Whether {day} fits ‘{wish}’ near {place} can't be said (values missing): {detail}."
    ),
    weather_others=" Other days that fit: {days}.",
    weather_no_others=" No other day in the next 14 days fits.",
    weather_data="Weather forecast for “{wish}” near {place}, days that fit: {days}",
    weather_fact_none="Weather forecast for “{wish}” near {place}: No day in the next 14 days fits.",
    weather_fact_misses="Weather forecast for “{wish}” near {place}: {day} does not fit “{wish}”.",
    weather_fact_down="Weather forecast not available.",
    weather_label="Weather forecast",
    weather_fact_unknown="Weather forecast for “{wish}” near {place}: Whether {day} fits can't be said (values missing).",
    weather_nopoint="Weather for {place} cannot be determined.",
    weather_window_found=(
        "Start dates that fit ‘{wish}’ at the day destinations ({n} days): {starts}; "
        "the plan starts on {first}"
    ),
    weather_window_none=(
        "No start date in the next 14 days fits ‘{wish}’ at the day destinations on all {n} "
        "days; at most {fits} of {n} days fit, starting {start}"
    ),
    weather_window_all="All {n} days fit ‘{wish}’ at the day destinations.",
    weather_window_part=(
        "{fits} of {n} days fit ‘{wish}’ at the day destinations; not confirmed: {days}."
    ),
)

TEXTS: dict[str, Texts] = {"de": DE, "en": EN}


def texts(lang: Lang) -> Texts:
    return TEXTS[lang]
