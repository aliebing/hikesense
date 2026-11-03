import { render, screen } from "@testing-library/react";

vi.mock("./AccountMenu", () => ({ default: () => <span>Konto</span> }));

import PageFrame from "./PageFrame";

it("lets the header wrap on narrow screens instead of cutting the last link", () => {
  render(
    <PageFrame back={{ href: "/", label: "← Zur Startseite" }} longDistance={[{ id: "westweg", name: "Westweg" }]}>
      <p>Inhalt</p>
    </PageFrame>,
  );
  expect(screen.getByRole("banner")).toHaveClass("flex-wrap");
  expect(screen.getByRole("navigation")).toHaveClass("flex-wrap");
  const home = screen.getByRole("link", { name: "HikeSense" });
  expect(home).toHaveClass("whitespace-nowrap");
  expect(home).toHaveAttribute("href", "/");
  expect(home.querySelector("svg[data-logo-mark='light']")).not.toBeNull();
  expect(screen.getByRole("link", { name: "← Zur Startseite" })).toHaveClass("whitespace-nowrap");
  expect(screen.getByText("Fernwege")).toHaveClass("whitespace-nowrap");
});

it("is dark green without photo backdrop or text shadows", () => {
  const { container } = render(
    <PageFrame>
      <p>Inhalt</p>
    </PageFrame>,
  );
  expect(container.firstElementChild).toHaveClass("from-[#0e2214]"); // very dark green towards black
  expect(container.firstElementChild!.className).toMatch(/\bto-(black|\[#0)/);
  expect(container.querySelector("[class*='drop-shadow']")).toBeNull();
  expect(container.querySelector(".fixed")).toBeNull();
});
