import { render, screen, within } from "@testing-library/react";

vi.mock("../components/AccountMenu", () => ({ default: () => null }));

import ImpressumPage from "../app/impressum/page";
import DatenschutzPage from "../app/datenschutz/page";
import PageFrame from "../components/PageFrame";
import CreditsLine from "../components/CreditsLine";
import { renderWithLocale } from "../test-utils";
import { datenschutz } from "./datenschutz";
import { impressum } from "./impressum";
import { APP_NOTE } from "./site";

it("Impressum names provider, address and a mail link (German default)", () => {
  render(<ImpressumPage />);
  expect(screen.getByRole("heading", { level: 1, name: "Impressum" })).toBeInTheDocument();
  expect(screen.getByText("Alexander Liebing")).toBeInTheDocument();
  expect(screen.getByText("Panoramaweg 6")).toBeInTheDocument();
  expect(screen.getByText("76189 Karlsruhe")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "aliebing@gmx.de" })).toHaveAttribute("href", "mailto:aliebing@gmx.de");
});

it("English pages say the German version is binding", () => {
  renderWithLocale(<DatenschutzPage />, "en");
  expect(screen.getByRole("heading", { level: 1, name: "Privacy notice" })).toBeInTheDocument();
  expect(screen.getByText(/German version .* is binding/)).toBeInTheDocument();
});

it("privacy notice states the retention times the code uses", () => {
  const text = JSON.stringify(datenschutz("de"));
  expect(text).toContain("nach 30 Tagen automatisch gelöscht"); // HIKESENSE_LOG_RETENTION_DAYS default
  expect(text).toContain("nach 24 Stunden gelöscht"); // guest_quota WINDOW
  expect(text).toContain("hikesense.lang"); // i18n COOKIE_NAME
  expect(JSON.stringify(datenschutz("en"))).toContain("deleted automatically after 30 days");
});

it("both languages have the same sections", () => {
  for (const doc of [(l: "de" | "en") => impressum(l, "HikeSense", APP_NOTE), (l: "de" | "en") => datenschutz(l)]) {
    const de = doc("de"), en = doc("en");
    expect(en.sections.length).toBe(de.sections.length);
  }
});

it("every page frame links Impressum and privacy notice; the credit line does too", () => {
  const { unmount } = render(<PageFrame>x</PageFrame>);
  const footer = document.querySelector("footer[data-legal]") as HTMLElement;
  expect(within(footer).getByRole("link", { name: "Impressum" })).toHaveAttribute("href", "/impressum");
  expect(within(footer).getByRole("link", { name: "Datenschutz" })).toHaveAttribute("href", "/datenschutz");
  unmount();
  render(
    <PageFrame legalFooter={false}>
      <CreditsLine />
    </PageFrame>,
  );
  expect(document.querySelector("footer[data-legal]")).toBeNull();
  expect(screen.getByRole("link", { name: "Impressum" })).toBeInTheDocument();
});

it("a full stop after a link stays outside it", () => {
  render(<DatenschutzPage />);
  expect(screen.getByRole("link", { name: "https://www.baden-wuerttemberg.datenschutz.de" })).toHaveAttribute("href", "https://www.baden-wuerttemberg.datenschutz.de");
});
