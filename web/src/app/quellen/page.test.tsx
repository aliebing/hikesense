import { screen } from "@testing-library/react";
import { renderWithLocale } from "../../test-utils";
import Sources from "./page";

it("lists every source that must be credited, with its licence", () => {
  renderWithLocale(<Sources />, "de");
  expect(screen.getByRole("heading", { level: 1, name: "Quellen & Lizenzen" })).toBeInTheDocument();
  for (const text of [
    "© OpenStreetMap-Mitwirkende",
    "Copernicus DEM GLO-30",
    "Wikimedia Commons",
    "basemap.de",
    "Open-Meteo",
    "Wikipedia, Wikivoyage",
    "DIN 33466",
  ]) {
    expect(screen.getAllByText(new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))).length).toBeGreaterThan(0);
  }
  expect(screen.getByRole("link", { name: "ODbL" })).toHaveAttribute("href", "https://opendatacommons.org/licenses/odbl/");
  expect(screen.getByRole("link", { name: "← Zur Startseite" })).toHaveAttribute("href", "/");
});

it("in English", () => {
  renderWithLocale(<Sources />, "en");
  expect(screen.getByRole("heading", { level: 1, name: "Sources & licences" })).toBeInTheDocument();
  expect(screen.getByText(/Trails, places, inns/)).toBeInTheDocument();
});
