import { fireEvent, render } from "@testing-library/react";
import Backdrop from "./Backdrop";

const photo = { url: "https://img/a.jpg", thumb_url: "https://img/a-t.jpg", author: "Anna", license: "CC BY 4.0", license_url: null, page_url: null };

it("draws the photo decoratively behind the middle, fading out to the sides", () => {
  const { container } = render(<Backdrop photo={photo} />);
  const layer = container.firstElementChild as HTMLElement;
  expect(layer).toHaveAttribute("aria-hidden", "true");
  expect(layer.className).toContain("pointer-events-none");
  expect(layer.className).toContain("-z-10");
  expect(layer.className).not.toContain("fixed");
  expect(layer.className).not.toMatch(/max-w-/); // the whole width, fading out at the edges
  const img = container.querySelector("img")!;
  expect(img).toHaveAttribute("src", "https://img/a.jpg");
  const style = img.getAttribute("style")!;
  // a soft-edged rectangle, not an oval: sides and bottom fade, combined by intersecting two linear masks
  expect(style).not.toContain("radial-gradient");
  expect(style.match(/linear-gradient/g)?.length).toBeGreaterThanOrEqual(2);
  expect(style).toMatch(/mask-composite: intersect/);
  expect(img.className).not.toMatch(/opacity-/);
  const alphas = [...style.matchAll(/\/ (0?\.\d+)\)/g)].map((m) => Number(m[1]));
  expect(alphas.length).toBeGreaterThanOrEqual(3); // gradual, not a hard edge
});

it("renders nothing without a photo or when the image fails", () => {
  const { container, rerender } = render(<Backdrop photo={null} />);
  expect(container).toBeEmptyDOMElement();
  rerender(<Backdrop photo={photo} />);
  fireEvent.error(container.querySelector("img")!);
  expect(container).toBeEmptyDOMElement();
});
