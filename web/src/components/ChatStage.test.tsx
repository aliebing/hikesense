import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Photo } from "../lib/data";
import ChatStage from "./ChatStage";
import { CoverProvider } from "./CoverContext";
import PhotoSwitcher from "./PhotoSwitcher";

const bg: Photo = {
  url: "https://upload.example/bg.jpg",
  thumb_url: "https://upload.example/bg-t.jpg",
  author: "Hintergrund-Autor",
  license: "CC BY 4.0",
  license_url: null,
  page_url: null,
};

const results = {
  type: "results",
  fallback_reason: null,
  labels: {},
  cards: [
    {
      trail_id: "t1", name: "Feldsee-Runde", length_km: 12, ascent_m: 400, duration_h: 4, distance_km: 2,
      cover_thumb_url: "https://img/cover.jpg", cover_author: "Cover-Autorin", cover_license: "CC BY-SA 4.0",
      cover_license_url: null, cover_page_url: null, results: [],
      deviation_text: null, preference: { score: 0, met: [], missing: [], avoided_hit: [] },
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

it("the first tour's cover replaces the panorama background and is attributed there", async () => {
  const body = [results, { type: "done", usage: {}, unsupported: 0 }]
    .map((e) => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`)
    .join("");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 200 })));
  const { container } = render(
    <CoverProvider>
      <PhotoSwitcher photos={[bg]} />
      <ChatStage intro="Hi" />
    </CoverProvider>,
  );
  expect(container.querySelector('img[src="https://upload.example/bg.jpg"]')).not.toBeNull();
  await userEvent.type(screen.getByLabelText("Nachricht"), "Tour{Enter}");
  await screen.findByRole("link", { name: "Feldsee-Runde" });
  const stage = container.querySelector(".fixed.inset-0");
  // exactly one background layer, showing the cover; the old photo and its credit are gone
  expect(container.querySelectorAll(".fixed.inset-0")).toHaveLength(1);
  expect(stage?.querySelector("img")).toHaveAttribute("src", "https://img/cover.jpg");
  expect(container.querySelector('img[src="https://upload.example/bg.jpg"]')).toBeNull();
  expect(screen.queryByText(/Hintergrund-Autor/)).toBeNull();
  // the cover is credited both in the panorama and on the card
  expect(screen.getAllByText(/Cover-Autorin/)).toHaveLength(2);
});
