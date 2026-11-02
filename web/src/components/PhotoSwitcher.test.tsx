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

test("PhotoSwitcher without photos renders a bounded gradient fallback", () => {
  const { container } = render(<PhotoSwitcher photos={[]} />);
  expect(screen.getByTestId("photo-fallback")).toBeInTheDocument();
  expect(container.querySelector(".fixed")).toBeNull();
});

test("PhotoSwitcher is a bounded picture, never a fixed backdrop", () => {
  const { container } = render(<PhotoSwitcher photos={[p("a", "Anna"), p("b", "Ben")]} />);
  expect(container.querySelector(".fixed")).toBeNull();
  expect(container.querySelector("figure")).not.toBeNull();
});

test("backdrop variant fills the screen behind the page and keeps controls and credit", async () => {
  const { container } = render(<PhotoSwitcher photos={[p("a", "Anna"), p("b", "Ben")]} variant="backdrop" />);
  const layer = container.querySelector(".fixed");
  expect(layer).not.toBeNull();
  expect(layer!.querySelector("img")).toHaveAttribute("src", "https://upload.example/a.jpg");
  expect(container.querySelector("figure")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Nächstes Bild" }));
  expect(screen.getByText(/Ben/)).toBeInTheDocument();
});

test("PhotoSwitcher thumbnails pick the shown photo", async () => {
  render(<PhotoSwitcher photos={[p("a", "Anna"), p("b", "Ben")]} />);
  expect(screen.getByRole("button", { name: "Bild 1" })).toHaveAttribute("aria-current", "true");
  await userEvent.click(screen.getByRole("button", { name: "Bild 2" }));
  expect(document.querySelector("figure img[data-main]")).toHaveAttribute("src", "https://upload.example/b.jpg");
  expect(screen.getByText(/Ben/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Bild 2" })).toHaveAttribute("aria-current", "true");
});

describe("own photos", () => {
  const h = vi.hoisted(() => ({ session: null as null | { user: { id: string } }, list: vi.fn(), del: vi.fn() }));
  vi.mock("../lib/auth", () => ({
    useSession: () => ({ session: h.session, loading: false }),
    getBrowserSupabase: () => ({}),
  }));
  vi.mock("../lib/photo", () => ({ listOwnPhotos: h.list, deleteOwnPhoto: h.del, prepareUpload: vi.fn(), uploadOwnPhoto: vi.fn() }));

  const mine: Photo = { ...p("m", "Eigenes Foto"), license: "privat", license_url: null, page_url: null, own: { id: 7, path: "u1/t1/m.jpg" } };

  beforeEach(() => {
    h.list.mockReset();
    h.del.mockReset();
  });

  it("shows own photos only with a session and offers delete", async () => {
    h.session = null;
    const { unmount } = render(<PhotoSwitcher photos={[p("a", "Anna")]} trailId="t1" />);
    expect(h.list).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Nächstes Bild" })).toBeNull();
    unmount();

    h.session = { user: { id: "u1" } };
    h.list.mockResolvedValue([mine]);
    render(<PhotoSwitcher photos={[p("a", "Anna")]} trailId="t1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Nächstes Bild" }));
    expect(screen.getByText(/Foto: Eigenes Foto/)).toBeInTheDocument();
    h.list.mockResolvedValue([]);
    await userEvent.click(screen.getByRole("button", { name: "Foto löschen" }));
    expect(h.del).toHaveBeenCalledWith({}, { id: 7, path: "u1/t1/m.jpg" });
    expect(await screen.findByText(/Anna/)).toBeInTheDocument();
  });
});
