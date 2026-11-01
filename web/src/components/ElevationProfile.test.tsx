import { render, screen } from "@testing-library/react";
import ElevationProfile from "./ElevationProfile";

it("labels the profile with its lowest and highest point", () => {
  render(<ElevationProfile profile={[[0, 712], [2, 1023.4], [4, 800]]} />);
  expect(screen.getByRole("img", { name: "Höhenprofil · 712–1.023 m" })).toBeInTheDocument();
  expect(screen.getByText("Höhenprofil · 712–1.023 m")).toBeInTheDocument();
});
