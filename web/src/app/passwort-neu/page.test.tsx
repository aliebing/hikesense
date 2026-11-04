import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ set: vi.fn(), push: vi.fn(), session: { user: {} } as object | null }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: h.push, refresh: () => {} }) }));
vi.mock("../../lib/auth", () => ({
  checkBlocked: async () => false,
  onBlocked: () => () => {},
  reportBlocked: () => {},
  signOut: vi.fn(),
  useSession: () => ({ session: h.session, loading: false }),
  setNewPassword: h.set,
}));

import PasswortNeu from "./page";

beforeEach(() => {
  h.set.mockReset();
  h.push.mockReset();
  h.session = { user: {} };
});

async function type(a: string, b: string) {
  await userEvent.type(screen.getByLabelText("Neues Passwort"), a);
  await userEvent.type(screen.getByLabelText("Passwort wiederholen"), b);
  await userEvent.click(screen.getByRole("button", { name: "Passwort speichern" }));
}

it("mismatched passwords show an error and save nothing", async () => {
  render(<PasswortNeu />);
  await type("neues-pw-1", "neues-pw-2");
  expect(await screen.findByRole("alert")).toHaveTextContent("Die Passwörter stimmen nicht überein");
  expect(h.set).not.toHaveBeenCalled();
});

it("success navigates home", async () => {
  h.set.mockResolvedValue({ error: null });
  render(<PasswortNeu />);
  await type("neues-pw-1", "neues-pw-1");
  await waitFor(() => expect(h.push).toHaveBeenCalledWith("/"));
  expect(h.set).toHaveBeenCalledWith("neues-pw-1", "de");
});

it("without a recovery session the link has expired", () => {
  h.session = null;
  render(<PasswortNeu />);
  expect(screen.getByText(/Der Link ist abgelaufen/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Neuen Link anfordern" })).toHaveAttribute("href", "/passwort-vergessen");
  expect(screen.queryByLabelText("Neues Passwort")).toBeNull();
});
