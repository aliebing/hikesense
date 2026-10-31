import { render, screen } from "@testing-library/react";

vi.mock("./AccountMenu", () => ({ default: () => <span>Konto</span> }));

import Panorama from "./Panorama";

it("lets the header wrap on narrow screens instead of cutting the last link", () => {
  render(
    <Panorama back={{ href: "/", label: "← Zur Startseite" }} longDistance={[{ id: "westweg", name: "Westweg" }]}>
      <p>Inhalt</p>
    </Panorama>,
  );
  expect(screen.getByRole("banner")).toHaveClass("flex-wrap");
  expect(screen.getByRole("navigation")).toHaveClass("flex-wrap");
  expect(screen.getByRole("link", { name: "Hike all about" })).toHaveClass("whitespace-nowrap");
  expect(screen.getByRole("link", { name: "← Zur Startseite" })).toHaveClass("whitespace-nowrap");
  expect(screen.getByText("Fernwege")).toHaveClass("whitespace-nowrap");
});
