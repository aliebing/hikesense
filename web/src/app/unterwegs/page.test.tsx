import { render, screen, within } from "@testing-library/react";

const h = vi.hoisted(() => ({ session: null as null | object, query: "plan=p1&day=2" }));
vi.mock("../../lib/auth", () => ({ useSession: () => ({ session: h.session, loading: false }), getBrowserSupabase: () => ({}) }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(h.query) }));

import UnterwegsPage from "./page";

it("plan without session: hint with link to /anmelden", () => {
  h.session = null;
  render(<UnterwegsPage />);
  expect(screen.getByText(/Für einen gemerkten Plan/)).toHaveTextContent("Anmelden");
  expect(within(screen.getByText(/Für einen gemerkten Plan/)).getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/anmelden");
});

it("no trail and no plan: says nothing is selected", () => {
  h.query = "";
  render(<UnterwegsPage />);
  expect(screen.getByText(/Keine Tour ausgewählt/)).toBeInTheDocument();
});
