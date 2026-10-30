const h = vi.hoisted(() => ({
  insert: vi.fn(),
  order: vi.fn(),
  eq: vi.fn(),
  from: vi.fn(),
}));
vi.mock("./auth", () => ({ getBrowserSupabase: () => ({ from: h.from }) }));

import { deletePlan, listPlans, savePlan } from "./plans";

beforeEach(() => {
  vi.clearAllMocks();
  h.from.mockImplementation(() => ({
    insert: h.insert,
    select: () => ({ order: h.order }),
    delete: () => ({ eq: h.eq }),
  }));
});

it("saves the card payload unchanged", async () => {
  h.insert.mockResolvedValue({ error: null });
  const payload = { trail_id: "t1", name: "Feldsee-Runde", length_km: 12.3 };
  expect(await savePlan("day_hike", "Feldsee-Runde", payload)).toEqual({ error: null });
  expect(h.from).toHaveBeenCalledWith("saved_plans");
  expect(h.insert).toHaveBeenCalledWith({ kind: "day_hike", title: "Feldsee-Runde", payload });
  expect(h.insert.mock.calls[0][0].payload).toBe(payload);
});

it("reports a German error when saving fails", async () => {
  h.insert.mockResolvedValue({ error: { message: "boom" } });
  expect((await savePlan("multiday", "x", {})).error).toMatch(/Merken/);
  h.insert.mockRejectedValue(new Error("offline"));
  expect((await savePlan("multiday", "x", {})).error).toMatch(/Merken/);
});

it("lists and deletes own plans", async () => {
  const rows = [{ id: "p1", kind: "day_hike", title: "A", payload: {}, created_at: "2026-10-30T10:00:00Z" }];
  h.order.mockResolvedValue({ data: rows, error: null });
  expect(await listPlans()).toEqual({ plans: rows, error: null });
  expect(h.order).toHaveBeenCalledWith("created_at", { ascending: false });
  h.eq.mockResolvedValue({ error: null });
  expect(await deletePlan("p1")).toEqual({ error: null });
  expect(h.eq).toHaveBeenCalledWith("id", "p1");
});

it("list failure gives an empty list and a message", async () => {
  h.order.mockResolvedValue({ data: null, error: { message: "x" } });
  const r = await listPlans();
  expect(r.plans).toEqual([]);
  expect(r.error).toMatch(/geladen/);
});
