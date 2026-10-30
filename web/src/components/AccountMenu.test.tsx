import { render, screen } from "@testing-library/react";

const h = vi.hoisted(() => ({ session: null as null | { user: { email: string } }, signOut: vi.fn() }));
vi.mock("../lib/auth", () => ({ useSession: () => ({ session: h.session, loading: false }), signOut: h.signOut }));

import AccountMenu from "./AccountMenu";

it("offers sign-in without a session", () => {
  h.session = null;
  render(<AccountMenu />);
  expect(screen.getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/anmelden");
});

it("shows a shortened e-mail and Abmelden with a session", () => {
  h.session = { user: { email: "ein.sehr.langer.name@example.com" } };
  render(<AccountMenu />);
  expect(screen.getByText("ein.sehr.langer.name…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
});
