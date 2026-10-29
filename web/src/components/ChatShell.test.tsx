import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatShell from "./ChatShell";

const sse = (events: object[]) =>
  events.map((e) => `event: ${(e as { type: string }).type}\ndata: ${JSON.stringify(e)}\n\n`).join("");

function mockStream(body: string) {
  const bytes = new TextEncoder().encode(body);
  const stream = new ReadableStream({
    start(c) {
      c.enqueue(bytes);
      c.close();
    },
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream, { status: 200 })));
}

const request = {
  intent: "day_hike", activity: "hike", start_text: null, start: null, constraints: [
    { kind: "length_km", min: null, max: 15, required: null },
  ], preferences: [{ tag_id: "aussicht", mode: "prefer", weight: 3 }], pace_min_per_km: null,
  unmatched: ["Hundefreundlich"], question: null,
};
const understood = { type: "understood", text: "Verstanden: Tagestour, Wandern.", request };
const tour = {
  trail_id: "t1", name: "Feldsee-Runde", length_km: 12, ascent_m: 400, duration_h: 4, distance_km: 2,
  cover_thumb_url: "https://img/x.jpg", results: [], deviation_text: null,
  preference: { score: 0, met: [], missing: [], avoided_hit: [] },
};

afterEach(() => vi.unstubAllGlobals());

async function ask(text = "Tour bitte") {
  await userEvent.type(screen.getByLabelText("Nachricht"), `${text}{Enter}`);
}

it("shows understood chips including 'nicht prüfbar'", async () => {
  mockStream(sse([understood, { type: "done", usage: {}, unsupported: 0 }]));
  render(<ChatShell intro="Hi" apiUrl="http://api" />);
  await ask();
  expect(await screen.findByText("Länge ≤ 15 km")).toBeInTheDocument();
  expect(screen.getByText(/Vorliebe: aussicht/)).toBeInTheDocument();
  expect(screen.getByText("nicht prüfbar: Hundefreundlich")).toBeInTheDocument();
  expect(screen.getByText("Tour bitte")).toBeInTheDocument();
});

it("shows fallback reason above cards and reports the cover of the first tour", async () => {
  const onCover = vi.fn();
  mockStream(
    sse([
      understood,
      { type: "results", cards: [tour], fallback_reason: "Keine Tour erfüllt alle Wünsche, weil …" },
      { type: "done", usage: {}, unsupported: 0 },
    ]),
  );
  render(<ChatShell intro="Hi" apiUrl="http://api" onCover={onCover} />);
  await ask();
  const note = await screen.findByRole("note");
  const card = screen.getByRole("link", { name: "Feldsee-Runde" });
  expect(note.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(onCover).toHaveBeenCalledWith("https://img/x.jpg");
});

it("streams tokens, shows sources with a draft marker", async () => {
  mockStream(
    sse([
      { type: "token", text: "Der " },
      { type: "token", text: "Feldberg." },
      { type: "sources", sources: [{ id: "s", name: "Quelle A", url: "https://a", license: "CC BY", status: "entwurf" }] },
      { type: "done", usage: {}, unsupported: 0 },
    ]),
  );
  render(<ChatShell intro="Hi" apiUrl="http://api" />);
  await ask();
  expect(await screen.findByText("Der Feldberg.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Quelle A" })).toHaveAttribute("href", "https://a");
  expect(screen.getByText(/Lizenz: CC BY/)).toBeInTheDocument();
  expect(screen.getByText("Entwurf")).toBeInTheDocument();
});

it("clarify options are buttons that send the answer", async () => {
  mockStream(sse([{ type: "clarify", question: "Welcher Feldberg?", options: ["Gipfel", "Gemeinde"] }]));
  render(<ChatShell intro="Hi" apiUrl="http://api" />);
  await ask("Feldberg");
  mockStream(sse([{ type: "token", text: "ok" }]));
  await userEvent.click(await screen.findByRole("button", { name: "Gipfel" }));
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string);
  expect(body.message).toBe("Gipfel");
  expect(body.thread_id).toMatch(/^[0-9a-f-]{36}$/);
});

it("shows a German error when the API is unreachable and keeps the input usable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
  render(<ChatShell intro="Hi" apiUrl="http://api" />);
  await ask();
  expect(await screen.findByRole("alert")).toHaveTextContent(/nicht erreichbar/);
  expect(screen.getByLabelText("Nachricht")).toBeEnabled();
});
