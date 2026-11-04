import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ reset: vi.fn() }));
vi.mock("../../lib/auth", () => ({
  checkBlocked: async () => false,
  onBlocked: () => () => {},
  reportBlocked: () => {},
  signOut: vi.fn(),
  useSession: () => ({ session: null, loading: false }),
  requestPasswordReset: h.reset,
}));

import PasswortVergessen from "./page";

const NEUTRAL = "Wenn es ein Konto mit dieser Adresse gibt, haben wir dir einen Link geschickt.";

it("sends the reset request and shows the neutral notice", async () => {
  h.reset.mockResolvedValue({ error: null, notice: NEUTRAL });
  render(<PasswortVergessen />);
  await userEvent.type(screen.getByLabelText("E-Mail"), "a@b.de");
  await userEvent.click(screen.getByRole("button", { name: "Link senden" }));
  expect(await screen.findByRole("status")).toHaveTextContent(NEUTRAL);
  expect(h.reset).toHaveBeenCalledWith("a@b.de", "de");
});

it("shows an error only when the service is unreachable", async () => {
  h.reset.mockResolvedValue({ error: "Die Anmeldung ist gerade nicht erreichbar" });
  render(<PasswortVergessen />);
  await userEvent.type(screen.getByLabelText("E-Mail"), "a@b.de");
  await userEvent.click(screen.getByRole("button", { name: "Link senden" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("nicht erreichbar");
});
