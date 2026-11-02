import { render, screen } from "@testing-library/react";
import SearchTable from "./SearchTable";
import { renderWithLocale } from "../../test-utils";

it("shows a dash as cost sum when no cost was reported", () => {
  render(<SearchTable page={{ items: [], total: 0, sums: { count: 2, cost_usd: null, avg_duration_ms: 1000 } }} selected={null} onSelect={() => {}} onMore={() => {}} />);
  expect(screen.getByText("Summe: 2 Suchen · – · Ø 1,0 s")).toBeInTheDocument();
});

it("shows the total row in English", () => {
  renderWithLocale(<SearchTable page={{ items: [], total: 0, sums: { count: 1234, cost_usd: 0.41, avg_duration_ms: 3600 } }} selected={null} onSelect={() => {}} onMore={() => {}} />, "en");
  expect(screen.getByText("Total: 1,234 searches · $0.4100 · avg 3.6 s")).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Tokens" })).toBeInTheDocument();
});

it("the card heading is dark on the light card (no light-on-dark text field class)", () => {
  render(<SearchTable page={{ items: [], total: 0, sums: { count: 0, cost_usd: null, avg_duration_ms: null } }} selected={null} onSelect={() => {}} onMore={() => {}} />);
  expect(screen.getByRole("heading", { level: 2 }).className).not.toContain("schrift-feld");
});
