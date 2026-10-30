import { render, screen } from "@testing-library/react";

const h = vi.hoisted(() => ({ session: null as null | object }));
vi.mock("../../lib/auth", () => ({ useSession: () => ({ session: h.session, loading: false }), getBrowserSupabase: () => ({}) }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams("id=p1") }));

import PlanPage from "./page";

it("signed out: hint with link to /anmelden", () => {
  render(<PlanPage />);
  expect(screen.getByText(/Zum Ansehen deines Plans/)).toHaveTextContent("Anmelden");
});
