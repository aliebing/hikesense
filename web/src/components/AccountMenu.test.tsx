import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ session: null as null | { user: { email: string } }, signOut: vi.fn() }));
vi.mock("../lib/auth", () => ({ useSession: () => ({ session: h.session, loading: false }), signOut: h.signOut }));
const chat = vi.hoisted(() => ({ reset: vi.fn() }));
vi.mock("./ChatProvider", () => ({ useResetChat: () => chat.reset }));

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

it("links to Meine Pläne with a session", () => {
  h.session = { user: { email: "a@b.de" } };
  render(<AccountMenu />);
  expect(screen.getByRole("link", { name: "Meine Pläne" })).toHaveAttribute("href", "/meine-plaene");
});

it("Abmelden also resets the conversation", async () => {
  h.session = { user: { email: "a@b.de" } };
  h.signOut.mockResolvedValue({ error: null });
  render(<AccountMenu />);
  await userEvent.click(screen.getByRole("button", { name: "Abmelden" }));
  expect(h.signOut).toHaveBeenCalled();
  expect(chat.reset).toHaveBeenCalled();
});

it("keeps the header narrow on phones: e-mail only from sm up, links never break inside", () => {
  h.session = { user: { email: "smoke@hikeall.local" } };
  render(<AccountMenu />);
  expect(screen.getByText("smoke@hikeall.local")).toHaveClass("hidden", "sm:inline");
  expect(screen.getByRole("link", { name: "Meine Pläne" })).toHaveClass("whitespace-nowrap");
  expect(screen.getByRole("button", { name: "Abmelden" })).toHaveClass("whitespace-nowrap");
});
