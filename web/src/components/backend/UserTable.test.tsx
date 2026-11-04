import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UserTable from "./UserTable";
import type { BackendUser } from "../../lib/backend";

const users: BackendUser[] = [
  { user_id: "u1", email: "anna@x.de", status: "aktiv", created_at: "2026-11-01T09:00:00Z", last_sign_in_at: "2026-11-03T10:00:00Z", searches: 2 },
  { user_id: "u2", email: "ben@x.de", status: "gesperrt", created_at: "2026-11-01T09:00:00Z", last_sign_in_at: null, searches: 0 },
  { user_id: "u3", email: "neu@x.de", status: "unbestätigt", created_at: "2026-11-02T09:00:00Z", last_sign_in_at: null, searches: 0 },
  { user_id: "guest", email: null, status: "gast", created_at: null, last_sign_in_at: null, searches: 5 },
];

const reply = (status: number, body: unknown) => ({ ok: status < 300, status, json: async () => body }) as Response;

beforeEach(() => vi.restoreAllMocks());

const rowOf = (text: string) => screen.getByText(text).closest("tr") as HTMLElement;

it("shows status, dates and search count per user", () => {
  render(<UserTable users={users} />);
  const anna = within(rowOf("anna@x.de"));
  expect(anna.getByText("aktiv")).toBeInTheDocument();
  expect(anna.getByText("2")).toBeInTheDocument();
  expect(within(rowOf("ben@x.de")).getByText("gesperrt")).toBeInTheDocument();
  expect(within(rowOf("neu@x.de")).getByText("unbestätigt")).toBeInTheDocument();
});

it("block asks for confirmation before calling the API", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, { status: "gesperrt" }));
  render(<UserTable users={users} />);
  await userEvent.click(within(rowOf("anna@x.de")).getByRole("button", { name: "Sperren" }));
  expect(f).not.toHaveBeenCalled();
  expect(within(rowOf("anna@x.de")).getByText("Wirklich sperren?")).toBeInTheDocument();
  await userEvent.click(within(rowOf("anna@x.de")).getByRole("button", { name: "Ja" }));
  expect(f.mock.calls[0][0]).toBe("/api/backend/users/u1/block");
  expect(await within(rowOf("anna@x.de")).findByText("gesperrt")).toBeInTheDocument();
  expect(within(rowOf("anna@x.de")).getByRole("button", { name: "Entsperren" })).toBeInTheDocument();
});

it("cancel does nothing", async () => {
  const f = vi.spyOn(globalThis, "fetch");
  render(<UserTable users={users} />);
  await userEvent.click(within(rowOf("anna@x.de")).getByRole("button", { name: "Sperren" }));
  await userEvent.click(within(rowOf("anna@x.de")).getByRole("button", { name: "Abbrechen" }));
  expect(f).not.toHaveBeenCalled();
  expect(within(rowOf("anna@x.de")).getByRole("button", { name: "Sperren" })).toBeInTheDocument();
});

it("unblock a blocked user", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, { status: "aktiv" }));
  render(<UserTable users={users} />);
  await userEvent.click(within(rowOf("ben@x.de")).getByRole("button", { name: "Entsperren" }));
  await userEvent.click(within(rowOf("ben@x.de")).getByRole("button", { name: "Ja" }));
  expect(f.mock.calls[0][0]).toBe("/api/backend/users/u2/unblock");
  expect(await within(rowOf("ben@x.de")).findByText("aktiv")).toBeInTheDocument();
});

it("shows the error and keeps the status when the action fails", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(502, { detail: "x" }));
  render(<UserTable users={users} />);
  await userEvent.click(within(rowOf("anna@x.de")).getByRole("button", { name: "Sperren" }));
  await userEvent.click(within(rowOf("anna@x.de")).getByRole("button", { name: "Ja" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Fehler 502");
  expect(within(rowOf("anna@x.de")).getByText("aktiv")).toBeInTheDocument();
});

it("guest row has no block button", () => {
  render(<UserTable users={users} />);
  const guest = within(rowOf("Gäste"));
  expect(guest.queryByRole("button")).toBeNull();
});
