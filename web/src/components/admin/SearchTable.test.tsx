import { render, screen } from "@testing-library/react";
import SearchTable from "./SearchTable";

it("shows a dash as cost sum when no cost was reported", () => {
  render(<SearchTable page={{ items: [], total: 0, sums: { count: 2, cost_usd: null, avg_duration_ms: 1000 } }} selected={null} onSelect={() => {}} onMore={() => {}} />);
  expect(screen.getByText("Summe: 2 Suchen · – · Ø 1,0 s")).toBeInTheDocument();
});
