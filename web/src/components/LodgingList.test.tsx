import { render, screen } from "@testing-library/react";
import type { LodgingOnTrail } from "../lib/data";
import LodgingList from "./LodgingList";

const l = (id: number, dist_m: number | null, website: string | null = null): LodgingOnTrail => ({ id, name: `Haus ${id}`, kind: "hotel", website, dist_m, along_km: id, lon: 8, lat: 48 });

it("shows the five nearest lodgings, nearest first, with a link", () => {
  render(<LodgingList lodgings={[l(1, 900), l(2, 120, "https://haus2.example"), l(3, null), l(4, 300), l(5, 500), l(6, 700), l(7, 800)]} />);
  const items = screen.getAllByRole("listitem");
  expect(items).toHaveLength(5);
  expect(items[0]).toHaveTextContent("Haus 2");
  expect(items[0]).toHaveTextContent("120 m vom Weg");
  expect(screen.getByRole("link", { name: "Website" })).toHaveAttribute("href", "https://haus2.example/");
  expect(screen.getAllByRole("link", { name: "Suchen" }).length).toBe(4);
  expect(screen.getByText("Verfügbarkeit bitte auf der Website prüfen")).toBeInTheDocument();
});

it("renders nothing without lodgings", () => {
  const { container } = render(<LodgingList lodgings={[]} />);
  expect(container).toBeEmptyDOMElement();
});
