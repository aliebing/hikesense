import { screen, within } from "@testing-library/react";
import { renderWithLocale } from "../test-utils";
import WeatherDays from "./WeatherDays";
import type { WeatherDaysData } from "../lib/chat";

const day = (date: string, match: boolean | null, over: Record<string, unknown> = {}) => ({
  date,
  match,
  weather: { date, code: 0, text: "Klar", t_min_c: 2, t_max_c: 11.4, precip_mm: 0, precip_prob_pct: 5, snowfall_cm: 0, source_id: "open-meteo", ...over },
});

const data = (over: Partial<WeatherDaysData> = {}): WeatherDaysData => ({
  wish: "fine",
  place: "Feldberg",
  days: [day("2026-11-05", true), day("2026-11-06", false, { text: "Regen", precip_mm: 6.25, precip_prob_pct: 90 }), day("2026-11-07", null, { precip_mm: null })],
  best_only: false,
  note: null,
  ...over,
});

test("German: weekday and date, values, check mark only on fitting days, source", () => {
  renderWithLocale(<WeatherDays data={data()} />, "de");
  const list = screen.getByRole("list", { name: "Wetter" });
  const items = within(list).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("Do., 05.11.2026");
  expect(items[0]).toHaveTextContent("Klar · 2 / 11 °C · Regen 5 % / 0 mm");
  expect(items[0]).toHaveTextContent("✓ passt");
  expect(items[1]).not.toHaveTextContent("✓");
  expect(items[1]).toHaveTextContent("Regen 90 % / 6,3 mm");
  expect(items[2]).toHaveTextContent("Regen 5 % / unbekannt");
  expect(items[2]).toHaveTextContent("?");
  expect(screen.getByText("Tage für schönes Wetter bei Feldberg")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open-Meteo.com" })).toHaveAttribute("href", "https://open-meteo.com/");
});

test("English: English date and number format (day first, like the rest of the app)", () => {
  renderWithLocale(<WeatherDays data={data({ wish: "dry" })} />, "en");
  const items = within(screen.getByRole("list", { name: "Weather" })).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("Thu, 05/11/2026");
  expect(items[0]).toHaveTextContent("✓ fits");
  expect(items[1]).toHaveTextContent("Rain 90% / 6.3 mm");
  expect(screen.getByText("Days for dry weather near Feldberg")).toBeInTheDocument();
});

test("snow is shown when the day has snowfall; best_only says so and the note is shown", () => {
  renderWithLocale(
    <WeatherDays data={data({ wish: "snow", best_only: true, note: "Nur 7 Tage Vorhersage", days: [day("2026-11-05", false, { snowfall_cm: 0.4 })] })} />,
    "de",
  );
  expect(screen.getByText(/Kein Tag im Vorhersagezeitraum passt zu Schnee/)).toBeInTheDocument();
  expect(screen.getByText("Nur 7 Tage Vorhersage")).toBeInTheDocument();
  expect(screen.getByRole("listitem")).toHaveTextContent("Schnee 0,4 cm");
});

test("renders nothing without days and without a note", () => {
  const { container } = renderWithLocale(<WeatherDays data={data({ days: [] })} />, "de");
  expect(container).toBeEmptyDOMElement();
});
