import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ session: null as null | { user: { email: string } }, signOut: vi.fn(), blocked: false, listeners: [] as (() => void)[], push: vi.fn() }));
vi.mock("../lib/auth", () => ({
  useSession: () => ({ session: h.session, loading: false }),
  signOut: h.signOut,
  checkBlocked: async () => h.blocked,
  onBlocked: (cb: () => void) => { h.listeners.push(cb); return () => { h.listeners = h.listeners.filter((x) => x !== cb); }; },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: h.push, refresh: () => {} }) }));
const chat = vi.hoisted(() => ({ reset: vi.fn() }));
vi.mock("./ChatProvider", () => ({ useResetChat: () => chat.reset }));


import AccountMenu from "./AccountMenu";

beforeEach(() => { vi.restoreAllMocks(); h.blocked = false; h.listeners = []; h.push.mockReset(); h.signOut.mockReset(); h.signOut.mockResolvedValue({ error: null }); chat.reset.mockReset(); });

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
  h.session = { user: { email: "smoke@hikesense.local" } };
  render(<AccountMenu />);
  expect(screen.getByText("smoke@hikesense.local")).toHaveClass("hidden", "sm:inline");
  expect(screen.getByRole("link", { name: "Meine Pläne" })).toHaveClass("whitespace-nowrap");
  expect(screen.getByRole("button", { name: "Abmelden" })).toHaveClass("whitespace-nowrap");
});

it("never links to the backend and never asks it", () => {
  const f = vi.spyOn(globalThis, "fetch");
  h.session = { user: { email: "a@b.de" } };
  render(<AccountMenu />);
  expect(screen.queryByRole("link", { name: "Backend" })).toBeNull();
  expect(document.querySelector('a[href*="backend"], a[href*="admin"]')).toBeNull();
  expect(f.mock.calls.some((c) => String(c[0]).includes("backend"))).toBe(false);
});


it("a blocked session is signed out, the chat reset and the page sent to the sign-in notice", async () => {
  h.session = { user: { email: "a@b.de" } };
  h.blocked = true;
  render(<AccountMenu />);
  await waitFor(() => expect(h.push).toHaveBeenCalledWith("/anmelden?gesperrt=1"));
  expect(h.signOut).toHaveBeenCalled();
  expect(chat.reset).toHaveBeenCalled();
});

it("a block reported later (chat, saving) does the same", async () => {
  h.session = { user: { email: "a@b.de" } };
  render(<AccountMenu />);
  await waitFor(() => expect(h.listeners.length).toBe(1));
  expect(h.push).not.toHaveBeenCalled();
  h.listeners[0]();
  await waitFor(() => expect(h.push).toHaveBeenCalledWith("/anmelden?gesperrt=1"));
});

it("an active session stays signed in", async () => {
  h.session = { user: { email: "a@b.de" } };
  render(<AccountMenu />);
  await new Promise((r) => setTimeout(r, 0));
  expect(h.signOut).not.toHaveBeenCalled();
  expect(h.push).not.toHaveBeenCalled();
});
