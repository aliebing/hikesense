import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({ session: null as object | null, save: vi.fn(), blocked: false, reported: 0 }));
vi.mock("../lib/auth", () => ({
  useSession: () => ({ session: h.session, loading: false }),
  checkBlocked: async () => h.blocked,
  reportBlocked: () => { h.reported += 1; },
}));
vi.mock("../lib/plans", async (orig) => ({ ...(await orig<typeof import("../lib/plans")>()), savePlan: h.save }));

import MerkenButton from "./MerkenButton";

beforeEach(() => {
  h.session = null;
  h.blocked = false;
  h.reported = 0;
  h.save.mockReset();
  window.history.replaceState(null, "", "/t/abc");
});

it("links to sign-in with next when signed out", () => {
  render(<MerkenButton kind="day_hike" title="X" payload={{}} />);
  expect(screen.getByRole("link", { name: "Zum Merken anmelden" })).toHaveAttribute("href", "/anmelden?next=%2Ft%2Fabc");
});

it("saves when signed in", async () => {
  h.session = { user: {} };
  h.save.mockResolvedValue({ error: null });
  render(<MerkenButton kind="day_hike" title="X" payload={{ a: 1 }} />);
  await userEvent.click(screen.getByRole("button"));
  await waitFor(() => expect(h.save).toHaveBeenCalledWith("day_hike", "X", { a: 1 }));
});

it("a failed save of a blocked account reports the block", async () => {
  h.session = { user: {} };
  h.blocked = true;
  h.save.mockResolvedValue({ error: "save" });
  render(<MerkenButton kind="day_hike" title="X" payload={{}} />);
  await userEvent.click(screen.getByRole("button"));
  await waitFor(() => expect(h.reported).toBe(1));
});
