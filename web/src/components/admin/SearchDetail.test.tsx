import { render, screen, within } from "@testing-library/react";
import type { SearchDetail as Detail } from "../../lib/admin";
import SearchDetail from "./SearchDetail";

const base: Detail = { request_id: "r1", ts: "2026-11-02T13:02:00Z", owner: "u1", email: "anna@example.org", intent: "day_hike", activity: "hike", tool_calls: 1, input_tokens: 3000, output_tokens: 400, cost_usd: 0.0021, duration_ms: 4200 };

const full: Detail = {
  ...base,
  message: "Rundtour Feldberg 15 km mit Einkehr",
  previous_messages: ["Hallo"],
  request: { intent: "day_hike", start: { label: "Feldberg" }, constraints: [{ kind: "length_km", max: 15 }, { kind: "roundtrip", required: true }], preferences: [{ tag_id: "einkehr", mode: "prefer" }, { tag_id: "bus", mode: "avoid" }] },
  answer: "Hier sind **drei** Touren.",
  grounding_unsupported: 1,
  grounding_unsupported_names: 2,
  unsat_claims_removed: 3,
  fallback_reason: "Nichts passt genau",
  candidates: [
    { trail_id: "a", name: "Feldberg-Steig", status: "shown", note: null, score: 0.92, met: ["einkehr"], missing: [], avoided: [], results: [{ kind: "length_km", ok: true, actual: 12.4 }, { kind: "roundtrip", ok: true, actual: true }] },
    { trail_id: "b", name: "Seebuck-Tour", status: "fallback", note: "etwas zu lang", score: 0.5, met: [], missing: ["einkehr"], avoided: [], results: [{ kind: "length_km", ok: null, actual: null }, { kind: "roundtrip", ok: true, actual: true }] },
    { trail_id: "n", name: "Jägersteig", status: "near_miss", note: "11,6 km statt höchstens 11,5 km", score: 0.3, met: [], missing: [], avoided: [], results: [{ kind: "length_km", ok: false, actual: 11.6 }, { kind: "roundtrip", ok: true, actual: true }] },
    { trail_id: "c", name: "Westweg Etappe 8", status: "rejected", note: "22,3 km", score: 0.1, met: [], missing: [], avoided: ["bus"], results: [{ kind: "length_km", ok: false, actual: 22.3 }, { kind: "roundtrip", ok: false, actual: false }] },
  ],
  llm_calls: [
    { step: "understand", model: "m1", messages: [{ role: "system", content: "Sei nett" }], output: { x: 1 }, input_tokens: 100, output_tokens: 10, cost_usd: 0.001, duration_ms: 1000 },
    { step: "answer", model: "m1", messages: [{ role: "user", content: "Frage" }], output: "ok", input_tokens: 200, output_tokens: 20, cost_usd: null, duration_ms: 2000 },
  ],
  tools: [{ name: "search_day_hikes", args: { near: "Feldberg" }, result: "x".repeat(1000), truncated: true }],
};

it("shows all blocks of a full row", () => {
  render(<SearchDetail d={full} />);
  expect(screen.getByText("Rundtour Feldberg 15 km mit Einkehr")).toBeInTheDocument();
  expect(screen.getByText("Hallo")).toBeInTheDocument();
  expect(screen.getByText("So verstanden")).toBeInTheDocument();
  expect(screen.getByText(/Ort: Feldberg · Länge ≤ 15,0 km · Rundweg: ja · Vorliebe: einkehr · ohne bus/)).toBeInTheDocument();
  expect(screen.getByText("drei")).toBeInTheDocument();
  expect(screen.getByText("Zahlenprüfung: 1 Zahlen ersetzt · 2 Namen markiert · 3 Aussagen entfernt")).toBeInTheDocument();
  expect(screen.getByText("Nichts passt genau")).toBeInTheDocument();
  expect(screen.getByText("Warum diese Touren?")).toBeInTheDocument();
  expect(screen.getByText("✓ 12,4")).toBeInTheDocument();
  expect(screen.getByText("✗ 22,3")).toBeInTheDocument();
  expect(screen.getByText("gezeigt")).toBeInTheDocument();
  expect(screen.getByText("Ausweich")).toBeInTheDocument();
  expect(screen.getByText("verworfen")).toBeInTheDocument();
  expect(screen.getByText("knapp daneben")).toBeInTheDocument();
  expect(screen.getByText("Jägersteig").closest("tr")).toHaveClass("bg-amber-50");
  expect(screen.getByText("Westweg Etappe 8").closest("tr")).toHaveClass("opacity-60");
  expect(screen.getByText("Tool-Aufrufe (1)")).toBeInTheDocument();
  expect(screen.getByText("gekürzt")).toBeInTheDocument();
  expect(screen.getByText("Prompt: understand")).toBeInTheDocument();
  expect(screen.getByText("Prompt: answer")).toBeInTheDocument();
  expect(screen.getByText("Sei nett")).toBeInTheDocument();
  expect(screen.getByText("0,0021 $", { selector: "td" })).toBeInTheDocument(); // sum row
});

it("shows at most 300 characters of a tool result outside the details", () => {
  render(<SearchDetail d={full} />);
  const item = screen.getByText("search_day_hikes").closest("li")!;
  const preview = item.querySelector("[data-testid=preview]")!;
  expect(preview.textContent!.length).toBeLessThanOrEqual(300);
  expect(within(item).getByText("x".repeat(1000), { selector: "details pre" })).toBeInTheDocument();
});

it("old row: only key figures and a note", () => {
  render(<SearchDetail d={base} />);
  expect(screen.getByText("Ältere Suche – nur Kennzahlen gespeichert")).toBeInTheDocument();
  expect(screen.queryByText("Warum diese Touren?")).not.toBeInTheDocument();
  expect(screen.getByText("0,0021 $", { selector: "td" })).toBeInTheDocument();
});

it("plan row shows the days", () => {
  render(<SearchDetail d={{ ...full, candidates: [], plan: { trail_name: "Westweg", days: [{ day: 1, length_km: 18.2, stop: { name: "Hütte Eck" } }, { day: 2, length_km: 10, stop: null }] } }} />);
  expect(screen.getByText("Westweg")).toBeInTheDocument();
  expect(screen.getByText("Tag 1 · 18,2 km · Hütte Eck")).toBeInTheDocument();
  expect(screen.getByText("Tag 2 · 10,0 km · Wegende")).toBeInTheDocument();
});

it("marks cut prompts and outputs as gekürzt", () => {
  const calls = [{ step: "answer", model: "m", messages: [{ role: "user", content: "lang", truncated: true }], output: "o", output_truncated: true, input_tokens: 1, output_tokens: 1, cost_usd: null, duration_ms: 1 }];
  render(<SearchDetail d={{ ...base, message: "x", llm_calls: calls, tools: [] }} />);
  expect(screen.getAllByText("gekürzt")).toHaveLength(2);
});

it("error line without answer is detailed, not an old line", () => {
  render(<SearchDetail d={{ ...base, message: "Hallo", error: "ValueError", llm_calls: [], tools: [] }} />);
  expect(screen.queryByText("Ältere Suche – nur Kennzahlen gespeichert")).not.toBeInTheDocument();
  expect(screen.getByText("Hallo")).toBeInTheDocument();
});

it("shows the weather day finder block from weather_days", () => {
  const w = {
    wish: "fine",
    place: "Feldberg",
    best_only: false,
    days: [
      { date: "2026-11-05", match: true, code: 0, t_min_c: 2, t_max_c: 11.4, precip_mm: 0, precip_prob_pct: 5, snowfall_cm: 0 },
      { date: "2026-11-06", match: null, code: null, t_min_c: null, t_max_c: null, precip_mm: null, precip_prob_pct: null, snowfall_cm: null },
    ],
  };
  render(<SearchDetail d={{ ...full, weather_days: w }} />);
  expect(screen.getByRole("heading", { name: "Wetter-Tagesfinder" })).toBeInTheDocument();
  expect(screen.getByText("Wunsch: schönes Wetter · Feldberg")).toBeInTheDocument();
  expect(screen.getByText(/^✓ Do\., 05\.11\.2026 · 2 \/ 11 °C · 5% \/ 0 mm · 0 cm$/)).toBeInTheDocument();
  expect(screen.getByText(/^\? .* · – \/ – °C/)).toBeInTheDocument();
});

it("shows the finder's note and the weather wish under 'understood'", () => {
  const w = { wish: "fine", place: "Feldberg", best_only: false, note: "Wetter gerade nicht abrufbar.", days: [] };
  const d = { ...full, request: { ...full.request, weather_wish: "fine" }, weather_days: w };
  render(<SearchDetail d={d} />);
  expect(screen.getByText("Wetter gerade nicht abrufbar.")).toBeInTheDocument();
  expect(screen.getByText(/Wetter: schönes Wetter/)).toBeInTheDocument();
});

it("shows no weather block without weather_days", () => {
  render(<SearchDetail d={full} />);
  expect(screen.queryByRole("heading", { name: "Wetter-Tagesfinder" })).not.toBeInTheDocument();
});
