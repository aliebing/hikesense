import { render, screen } from "@testing-library/react";
import GroupList from "./GroupList";
import type { GroupBrief } from "../lib/chat";

const g = (over: Partial<GroupBrief>): GroupBrief => ({
  name: "Schwarzwaldverein Hausach",
  kind: "wanderverein",
  place: "Hausach",
  url: "https://example.org/hausach",
  checked_at: "2026-10-02",
  stale: false,
  dist_km: 0.4,
  ...over,
});

test("shows Stand and marks veraltet", () => {
  render(
    <GroupList
      groups={[g({}), g({ name: "DAV Lahr", kind: "alpenverein", place: "Lahr", url: "https://example.org/lahr", stale: true, dist_km: 31.25 })]}
      note="Stand: 01.03.2026"
    />,
  );
  expect(screen.getByText(/Stand: 01\.03\.2026/)).toBeInTheDocument();
  const items = screen.getAllByRole("listitem");
  expect(items[0]).not.toHaveTextContent("veraltet");
  expect(items[0]).toHaveTextContent("Wanderverein · Hausach · 0,4 km");
  expect(items[1]).toHaveTextContent("veraltet");
  expect(screen.getByRole("link", { name: "DAV Lahr" })).toHaveAttribute("href", "https://example.org/lahr");
  expect(screen.getByRole("link", { name: "DAV Lahr" })).toHaveAttribute("rel", expect.stringContaining("noopener"));
});

test("renders nothing for an empty list", () => {
  const { container } = render(<GroupList groups={[]} note="Stand: 01.03.2026" />);
  expect(container).toBeEmptyDOMElement();
});

const AUTO = "automatisch geprüft (Seite und Name abgerufen), noch nicht von Hand bestätigt";

test("unconfirmed entries are labelled automatisch geprüft, never von Hand", () => {
  render(<GroupList groups={[g({ status: "vorschlag" }), g({ name: "Ohne Status", url: "https://example.org/x" })]} note="Stand: 01.03.2026" />);
  expect(screen.getByText(new RegExp(AUTO.replace(/[()]/g, "\\$&")))).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/von Hand (gepflegt|geprüft)/);
});

test("von Hand geprüft only for status geprüft", () => {
  render(<GroupList groups={[g({ status: "geprüft" })]} note="Stand: 01.03.2026" />);
  expect(screen.getByText(/von Hand geprüft/)).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("automatisch geprüft");
});

test("a mixed list names which entries were checked by hand", () => {
  render(<GroupList groups={[g({ status: "geprüft" }), g({ name: "Neu", url: "https://example.org/n", status: "vorschlag" })]} note="Stand: 01.03.2026" />);
  const items = screen.getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("von Hand geprüft");
  expect(items[1]).not.toHaveTextContent("von Hand geprüft");
  expect(document.body).toHaveTextContent("automatisch geprüft");
});
