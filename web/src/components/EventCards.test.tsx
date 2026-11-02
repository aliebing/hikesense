import { render, screen, within } from "@testing-library/react";
import { renderWithLocale } from "../test-utils";
import EventCards from "./EventCards";
import type { RaceField, VerifiedRace } from "../lib/chat";

const f = (value: string | null, quote: string | null = value): RaceField => ({ value, quote });

const race = (over: Partial<VerifiedRace> = {}): VerifiedRace => ({
  name: f("Dreisamtal-Halbmarathon 2027"),
  date: f("2027-04-18", "Sonntag, 18.04.2027"),
  place: f("Kirchzarten", "Start und Ziel: Sportplatz Kirchzarten"),
  distances: f("Halbmarathon (21,1 km)"),
  registration_url: f("https://anmeldung.example.org/dreisamtal-2027", "Jetzt online anmelden"),
  registration_deadline: f("2027-04-11", "Anmeldeschluss: 11.04.2027"),
  fee: f(null),
  source_url: "https://lauf.example.org/",
  day: "2027-04-18",
  ...over,
});

const NOTE = "Angaben ohne Gewähr – bitte beim Veranstalter prüfen. Gesucht am 30.10.2026.";

test("every field with its source link, „nicht angegeben“ for unverified fields, and the note", () => {
  render(<EventCards events={[race()]} fallback={[]} note={NOTE} />);
  const card = screen.getByRole("article", { name: "Dreisamtal-Halbmarathon 2027" });
  expect(card).toHaveTextContent("18.04.2027");
  expect(card).toHaveTextContent("Kirchzarten");
  expect(card).toHaveTextContent("Halbmarathon (21,1 km)");
  expect(card).toHaveTextContent("11.04.2027");
  const fee = within(card).getByText("Startgebühr").closest("div")!;
  expect(fee).toHaveTextContent("nicht angegeben");
  expect(within(fee).queryByRole("link")).toBeNull();
  // each verified field links to the page it is quoted from, the quote as title
  const sources = within(card).getAllByRole("link", { name: "Quelle" });
  expect(sources).toHaveLength(6);
  for (const a of sources) {
    expect(a).toHaveAttribute("href", "https://lauf.example.org/");
    expect(a).toHaveAttribute("rel", expect.stringContaining("noopener"));
  }
  expect(sources[1]).toHaveAttribute("title", expect.stringContaining("Sonntag, 18.04.2027")); // the date row
  expect(within(card).getByRole("link", { name: "Jetzt online anmelden" })).toHaveAttribute(
    "href",
    "https://anmeldung.example.org/dreisamtal-2027",
  );
  expect(screen.getByText(NOTE)).toBeInTheDocument();
});

test("a race without verified name is titled by its source host", () => {
  render(<EventCards events={[race({ name: f(null) })]} fallback={[]} note={NOTE} />);
  expect(screen.getByRole("article", { name: "Lauf auf lauf.example.org" })).toHaveTextContent("Name");
});

test("no race: calendar links to search yourself, plus the note", () => {
  render(
    <EventCards
      events={[]}
      fallback={[{ name: "BLV Veranstaltungstermine", url: "https://www.blv-online.de/laeufe/veranstaltungstermine" }]}
      note={NOTE}
    />,
  );
  expect(screen.queryAllByRole("article")).toHaveLength(0);
  const list = screen.getByRole("list", { name: "Laufkalender" });
  expect(within(list).getByRole("link", { name: "BLV Veranstaltungstermine" })).toHaveAttribute(
    "href",
    "https://www.blv-online.de/laeufe/veranstaltungstermine",
  );
  expect(screen.getByText(NOTE)).toBeInTheDocument();
});

test("a link that is not http(s) is never rendered as a link", () => {
  render(
    <EventCards
      events={[race({ source_url: "javascript:alert(1)", registration_url: f("javascript:alert(1)", "x") })]}
      fallback={[]}
      note={NOTE}
    />,
  );
  for (const a of screen.queryAllByRole("link")) expect(a.getAttribute("href")).not.toMatch(/^javascript:/);
});

test("English: field labels, dates and gaps are English", () => {
  renderWithLocale(<EventCards events={[race()]} fallback={[]} note={NOTE} />, "en");
  const card = screen.getByRole("article", { name: "Dreisamtal-Halbmarathon 2027" });
  expect(card).toHaveTextContent("Date");
  expect(card).toHaveTextContent("18/04/2027");
  expect(within(card).getByText("Entry fee").closest("div")!).toHaveTextContent("not stated");
  expect(within(card).getAllByRole("link", { name: "Source" }).length).toBeGreaterThan(0);
});
