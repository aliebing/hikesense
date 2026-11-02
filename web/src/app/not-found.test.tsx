import { screen } from "@testing-library/react";
import { renderWithLocale } from "../test-utils";

vi.mock("../components/AccountMenu", () => ({ default: () => null }));

import NotFound from "./not-found";
import ErrorPage from "./error";

it("not-found speaks English", () => {
  renderWithLocale(<NotFound />, "en");
  expect(screen.getByText("There is no such trail here.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "← Home" })).toHaveAttribute("href", "/");
});

it("not-found speaks German", () => {
  renderWithLocale(<NotFound />, "de");
  expect(screen.getByText("Diesen Weg gibt es hier nicht.")).toBeInTheDocument();
});

it("error page speaks English", () => {
  renderWithLocale(<ErrorPage error={new Error("x")} reset={() => {}} />, "en");
  expect(screen.getByText("Something went wrong.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});
