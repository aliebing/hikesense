import { screen } from "@testing-library/react";
import { renderWithLocale } from "../test-utils";
import Attribution from "./Attribution";

const own = { url: "u", thumb_url: "u", author: "Eigenes Foto", license: "privat", license_url: null, page_url: null };

it("own photos: the stored German values are shown through the catalog", () => {
  const { unmount } = renderWithLocale(<Attribution photo={own} />, "en");
  expect(screen.getByText(/Photo: Own photo · private/)).toBeInTheDocument();
  unmount();
  renderWithLocale(<Attribution photo={own} />, "de");
  expect(screen.getByText(/Foto: Eigenes Foto · privat/)).toBeInTheDocument();
});
