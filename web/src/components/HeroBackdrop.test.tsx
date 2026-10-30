import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HeroBackdrop from "./HeroBackdrop";
import type { Photo } from "../lib/data";

const photo = (n: number): Photo => ({
  url: `/p${n}.jpg`,
  thumb_url: `/t${n}.jpg`,
  author: `Autor ${n}`,
  license: `CC-${n}`,
  license_url: null,
  page_url: null,
});
const photos = [photo(1), photo(2), photo(3)];

// jsdom has no matchMedia.
function mockReduced(reduced: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: reduced && query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia;
}

beforeEach(() => {
  vi.useFakeTimers();
  mockReduced(false);
});
afterEach(() => vi.useRealTimers());

describe("HeroBackdrop", () => {
  it("shows the first photo with its attribution", () => {
    render(<HeroBackdrop photos={photos} />);
    expect(screen.getByText(/Autor 1/)).toBeInTheDocument();
    expect(screen.getByText(/CC-1/)).toBeInTheDocument();
  });

  it("advances after the interval", () => {
    render(<HeroBackdrop photos={photos} intervalMs={1000} />);
    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.getByText(/Autor 2/)).toBeInTheDocument();
    expect(screen.queryByText(/Autor 1/)).toBeNull();
    act(() => void vi.advanceTimersByTime(2000));
    expect(screen.getByText(/Autor 1/)).toBeInTheDocument();
  });

  it("reduced motion shows one still photo", () => {
    mockReduced(true);
    const { container } = render(<HeroBackdrop photos={photos} intervalMs={1000} />);
    act(() => void vi.advanceTimersByTime(3000));
    expect(screen.getByText(/Autor 1/)).toBeInTheDocument();
    expect(container.querySelector('[data-motion="still"]')).not.toBeNull();
  });

  it("without photos the forest gradient", () => {
    const { container } = render(<HeroBackdrop photos={[]} />);
    expect(container.querySelector(".wald-verlauf")).not.toBeNull();
    expect(screen.queryByText(/Foto:/)).toBeNull();
  });

  it("a broken image is skipped", () => {
    const { container } = render(<HeroBackdrop photos={photos} />);
    fireEvent.error(container.querySelector('img[src="/p1.jpg"]')!);
    expect(screen.getByText(/Autor 2/)).toBeInTheDocument();
  });

  it("keeps the attribution out of the background layer so its links are clickable", () => {
    const { container } = render(<HeroBackdrop photos={photos} />);
    const credit = screen.getByText(/Autor 1/);
    expect(credit.closest(".-z-10")).toBeNull();
    expect(container.querySelector(".-z-10")).not.toBeNull();
    expect(credit.closest(".fixed")).not.toBeNull();
  });

  it("changes photo half as often on a phone", () => {
    window.matchMedia = ((query: string) => ({
      matches: query.includes("max-width"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;
    render(<HeroBackdrop photos={photos} intervalMs={1000} />);
    act(() => void vi.advanceTimersByTime(1500));
    expect(screen.getByText(/Autor 1/)).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(1000));
    expect(screen.getByText(/Autor 2/)).toBeInTheDocument();
  });
});
