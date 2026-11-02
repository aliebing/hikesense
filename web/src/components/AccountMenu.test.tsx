import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ session: null as null | { user: { email: string } }, signOut: vi.fn() }));
vi.mock("../lib/auth", () => ({ useSession: () => ({ session: h.session, loading: false }), signOut: h.signOut }));
const chat = vi.hoisted(() => ({ reset: vi.fn() }));
vi.mock("./ChatProvider", () => ({ useResetChat: () => chat.reset }));

const adm = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("../lib/admin", () => ({ adminGet: adm.get }));

import AccountMenu from "./AccountMenu";

beforeEach(() => { adm.get.mockReset(); adm.get.mockResolvedValue({ ok: false, status: 403, message: "Kein Zugriff" }); });

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

it("shows Backend link only for admins", async () => {
  h.session = { user: { email: "admin@hikeall.local" } };
  adm.get.mockResolvedValue({ ok: true, data: { role: "admin" } });
  const { unmount } = render(<AccountMenu />);
  expect(await screen.findByRole("link", { name: "Backend" })).toHaveAttribute("href", "/admin");
  expect(adm.get).toHaveBeenCalledWith("/me");
  unmount();

  h.session = { user: { email: "smoke@hikeall.local" } };
  adm.get.mockResolvedValue({ ok: false, status: 403, message: "Kein Zugriff" });
  render(<AccountMenu />);
  await waitFor(() => expect(adm.get).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("link", { name: "Backend" })).toBeNull();
});

it("does not ask /me without a session", () => {
  h.session = null;
  render(<AccountMenu />);
  expect(adm.get).not.toHaveBeenCalled();
});
