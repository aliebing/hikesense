import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PhotoSwitcher from "./PhotoSwitcher";
import type { Photo } from "../lib/data";

const p = (id: string, author: string): Photo => ({
  url: `https://upload.example/${id}.jpg`,
  thumb_url: `https://upload.example/${id}-thumb.jpg`,
  author,
  license: "CC BY-SA 4.0",
  license_url: "https://creativecommons.org/licenses/by-sa/4.0",
  page_url: `https://commons.wikimedia.org/wiki/File:${id}.jpg`,
});

test("PhotoSwitcher cycles and shows attribution", async () => {
  render(<PhotoSwitcher photos={[p("a", "Anna"), p("b", "Ben")]} />);
  expect(screen.getByText(/Anna/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Nächstes Bild" }));
  expect(screen.getByText(/Ben/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Nächstes Bild" }));
  expect(screen.getByText(/Anna/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Vorheriges Bild" }));
  expect(screen.getByText(/Ben/)).toBeInTheDocument();
});

test("PhotoSwitcher shows licence with link", () => {
  render(<PhotoSwitcher photos={[p("a", "Anna")]} />);
  expect(screen.getByRole("link", { name: "CC BY-SA 4.0" })).toHaveAttribute(
    "href",
    "https://creativecommons.org/licenses/by-sa/4.0",
  );
});

test("PhotoSwitcher without photos renders gradient fallback", () => {
  render(<PhotoSwitcher photos={[]} />);
  expect(screen.getByTestId("panorama-fallback")).toBeInTheDocument();
});
