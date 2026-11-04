import { render, screen } from "@testing-library/react";

vi.mock("../../../lib/auth", () => ({
  checkBlocked: async () => false,
  onBlocked: () => () => {},
  reportBlocked: () => {},
  signOut: vi.fn(),
  useSession: () => ({ session: null, loading: false }),
}));

import Bestaetigt from "./page";

it("shows the confirmation and a link home", () => {
  render(<Bestaetigt />);
  expect(screen.getByText("Deine E-Mail ist bestätigt. Viel Spaß beim Planen!")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Zur Startseite" })).toHaveAttribute("href", "/");
});
