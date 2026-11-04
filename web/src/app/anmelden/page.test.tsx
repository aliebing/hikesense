import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ push: vi.fn(), signIn: vi.fn(), signUp: vi.fn(), resend: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: h.push, refresh: () => {} }) }));
vi.mock("../../lib/auth", async (orig) => ({
  resendConfirmation: h.resend,
  safeNext: (await orig<typeof import("../../lib/auth")>()).safeNext,
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

it("the field takes an e-mail address only and passes it unchanged", async () => {
  h.signIn.mockResolvedValue({ error: null });
  render(<Anmelden />);
  expect(screen.getByLabelText("E-Mail")).toHaveAttribute("type", "email");
  expect(screen.getByPlaceholderText("E-Mail")).toBeInTheDocument();
  await fill();
  await userEvent.click(screen.getAllByRole("button", { name: "Anmelden" })[0]);
  await waitFor(() => expect(h.signIn).toHaveBeenCalledWith("a@b.de", "geheim12", "de"));
});

it("shows the forgot-password link", () => {
  render(<Anmelden />);
  expect(screen.getByRole("link", { name: "Passwort vergessen?" })).toHaveAttribute("href", "/passwort-vergessen");
});

it("offers to resend the confirmation mail after sign-up", async () => {
  h.signUp.mockResolvedValue({ error: null, notice: "Bitte bestätige deine E-Mail-Adresse" });
  h.resend.mockResolvedValue({ error: null, notice: "Bestätigungsmail ist unterwegs." });
  render(<Anmelden />);
  await fill();
  await userEvent.click(screen.getByRole("button", { name: "Konto anlegen" }));
  await userEvent.click(await screen.findByRole("button", { name: "Bestätigungsmail erneut senden" }));
  expect(h.resend).toHaveBeenCalledWith("a@b.de", "de");
  expect(await screen.findByRole("status")).toHaveTextContent("Bestätigungsmail ist unterwegs.");
});

it("offers to resend when signing in unconfirmed", async () => {
  h.signIn.mockResolvedValue({ error: "Bitte bestätige deine E-Mail-Adresse" });
  render(<Anmelden />);
  await fill();
  await userEvent.click(screen.getAllByRole("button", { name: "Anmelden" })[0]);
  expect(await screen.findByRole("button", { name: "Bestätigungsmail erneut senden" })).toBeInTheDocument();
});

it("English: texts, and the language is passed to sign-in", async () => {
  const { renderWithLocale } = await import("../../test-utils");
  h.signIn.mockResolvedValue({ error: null });
  renderWithLocale(<Anmelden />, "en");
  expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  expect(screen.getByPlaceholderText("E-mail")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Forgot password?" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "← Back to chat" })).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("E-mail"), "a@b.de");
  await userEvent.type(screen.getByLabelText("Password"), "secret12");
  await userEvent.click(screen.getAllByRole("button", { name: "Sign in" })[0]);
  await waitFor(() => expect(h.signIn).toHaveBeenCalledWith("a@b.de", "secret12", "en"));
});

describe("return path and notices", () => {
  afterEach(() => window.history.replaceState(null, "", "/"));

  it("redirects to next after sign-in", async () => {
    window.history.replaceState(null, "", "/anmelden?next=%2Fgemerkt");
    h.signIn.mockResolvedValue({ error: null });
    render(<Anmelden />);
    await fill();
    await userEvent.click(screen.getAllByRole("button", { name: "Anmelden" })[0]);
    await waitFor(() => expect(h.push).toHaveBeenCalledWith("/gemerkt"));
  });

  it("ignores absolute next urls", async () => {
    window.history.replaceState(null, "", "/anmelden?next=https%3A%2F%2Fevil.example");
    h.signIn.mockResolvedValue({ error: null });
    render(<Anmelden />);
    await fill();
    await userEvent.click(screen.getAllByRole("button", { name: "Anmelden" })[0]);
    await waitFor(() => expect(h.push).toHaveBeenCalledWith("/"));
  });

  it("shows the blocked notice with ?gesperrt=1", async () => {
    window.history.replaceState(null, "", "/anmelden?gesperrt=1");
    render(<Anmelden />);
    expect(await screen.findByText("Dein Konto ist gesperrt.")).toBeInTheDocument();
  });

  it("shows a hint when sent here to save something", async () => {
    window.history.replaceState(null, "", "/anmelden?next=%2F");
    render(<Anmelden />);
    expect(await screen.findByText("Melde dich an, um Touren zu speichern.")).toBeInTheDocument();
  });
});
