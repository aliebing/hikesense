import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ push: vi.fn(), signIn: vi.fn(), signUp: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: h.push, refresh: () => {} }) }));
vi.mock("../../lib/auth", async (orig) => ({
  loginEmail: (await orig<typeof import("../../lib/auth")>()).loginEmail,
  signIn: h.signIn,
  signUp: h.signUp,
  signOut: vi.fn(),
  useSession: () => ({ session: null, loading: false }),
}));

import Anmelden from "./page";

async function fill() {
  await userEvent.type(screen.getByLabelText("E-Mail"), "a@b.de");
  await userEvent.type(screen.getByLabelText("Passwort"), "geheim12");
}

beforeEach(() => vi.clearAllMocks());

it("signs in and goes back to the chat", async () => {
  h.signIn.mockResolvedValue({ error: null });
  render(<Anmelden />);
  await fill();
  await userEvent.click(screen.getAllByRole("button", { name: "Anmelden" })[0]);
  await waitFor(() => expect(h.push).toHaveBeenCalledWith("/"));
  expect(h.signIn).toHaveBeenCalledWith("a@b.de", "geheim12", "de");
});

it("shows the German error and stays", async () => {
  h.signIn.mockResolvedValue({ error: "E-Mail oder Passwort falsch" });
  render(<Anmelden />);
  await fill();
  await userEvent.click(screen.getAllByRole("button", { name: "Anmelden" })[0]);
  expect(await screen.findByRole("alert")).toHaveTextContent("E-Mail oder Passwort falsch");
  expect(h.push).not.toHaveBeenCalled();
});

it("sign-up with confirmation shows the hint instead of redirecting", async () => {
  h.signUp.mockResolvedValue({ error: null, notice: "Bitte bestätige deine E-Mail-Adresse" });
  render(<Anmelden />);
  await fill();
  await userEvent.click(screen.getByRole("button", { name: "Konto anlegen" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Bitte bestätige deine E-Mail-Adresse");
  expect(h.push).not.toHaveBeenCalled();
});

it("signs in with a bare user name as <name>@hikeall.local", async () => {
  h.signIn.mockResolvedValue({ error: null });
  render(<Anmelden />);
  await userEvent.type(screen.getByLabelText("E-Mail"), "admin");
  await userEvent.type(screen.getByLabelText("Passwort"), "admin");
  await userEvent.click(screen.getAllByRole("button", { name: "Anmelden" })[0]);
  await waitFor(() => expect(h.signIn).toHaveBeenCalledWith("admin@hikeall.local", "admin", "de"));
});

it("English: texts, and the language is passed to sign-in", async () => {
  const { renderWithLocale } = await import("../../test-utils");
  h.signIn.mockResolvedValue({ error: null });
  renderWithLocale(<Anmelden />, "en");
  expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.getByPlaceholderText("E-mail or username")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "← Back to chat" })).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("E-mail"), "a@b.de");
  await userEvent.type(screen.getByLabelText("Password"), "secret12");
  await userEvent.click(screen.getAllByRole("button", { name: "Sign in" })[0]);
  await waitFor(() => expect(h.signIn).toHaveBeenCalledWith("a@b.de", "secret12", "en"));
});
