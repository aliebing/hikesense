import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({
  session: null as null | { user: { email: string } },
  loadPreferences: vi.fn(),
  setPreference: vi.fn(),
  blocked: false,
  report: vi.fn(),
}));
vi.mock("../../lib/auth", () => ({
  checkBlocked: async () => h.blocked,
  onBlocked: () => () => {},
  reportBlocked: h.report,
  useSession: () => ({ session: h.session, loading: false }),
  signOut: vi.fn(async () => ({ error: null })),
}));
vi.mock("../../lib/preferences", async (orig) => ({
  ...(await orig<typeof import("../../lib/preferences")>()),
  loadPreferences: h.loadPreferences,
  setPreference: h.setPreference,
}));

import Vorlieben from "./page";

beforeEach(() => {
  vi.clearAllMocks();
  h.blocked = false;
  h.session = { user: { email: "a@b.de" } };
  h.loadPreferences.mockResolvedValue({ prefs: [{ tag_id: "feature:aussicht", mode: "prefer", weight: 3 }], error: null });
  h.setPreference.mockResolvedValue({ error: null });
});

it("asks to sign in without a session and loads nothing", () => {
  h.session = null;
  render(<Vorlieben />);
  expect(screen.getByText(/Um deine Vorlieben einzustellen/)).toBeInTheDocument();
  expect(h.loadPreferences).not.toHaveBeenCalled();
});

it("lists all nine features with what they mean and the saved choice", async () => {
  render(<Vorlieben />);
  const view = await screen.findByRole("radiogroup", { name: "Aussicht" });
  expect(within(view).getByRole("radio", { name: "Bevorzugen" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByRole("radio", { name: "deutlich" })).toHaveAttribute("aria-checked", "true");
  expect(screen.getByText(/Aussichtspunkt höchstens 300 m vom Weg/)).toBeInTheDocument();
  expect(screen.getAllByRole("radiogroup", { name: /^[^:]+$/ })).toHaveLength(9);
});

it("saves a new choice with the default weight and can reset it to Egal", async () => {
  render(<Vorlieben />);
  const inn = await screen.findByRole("radiogroup", { name: "Einkehr" });
  await userEvent.click(within(inn).getByRole("radio", { name: "Meiden" }));
  await waitFor(() => expect(h.setPreference).toHaveBeenCalledWith("feature:einkehr", { mode: "avoid", weight: 2 }));
  expect(await screen.findByText(/Gespeichert\./)).toBeInTheDocument();
  await userEvent.click(within(inn).getByRole("radio", { name: "Egal" }));
  await waitFor(() => expect(h.setPreference).toHaveBeenLastCalledWith("feature:einkehr", null));
});

it("a blocked account is reported instead of showing a save error", async () => {
  h.blocked = true;
  h.setPreference.mockResolvedValue({ error: "save" });
  render(<Vorlieben />);
  const inn = await screen.findByRole("radiogroup", { name: "Einkehr" });
  await userEvent.click(within(inn).getByRole("radio", { name: "Bevorzugen" }));
  await waitFor(() => expect(h.report).toHaveBeenCalled());
});
