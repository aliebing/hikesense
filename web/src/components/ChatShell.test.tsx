import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatShell from "./ChatShell";
import { ChatProvider } from "./ChatProvider";

const renderChat = () =>
  render(
    <ChatProvider apiUrl="http://api">
      <ChatShell intro="Hi" />
    </ChatProvider>,
  );

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
const understood = {
  type: "understood", text: "Verstanden: Tagestour, Wandern.", request, labels: { aussicht: "Aussicht" },
};
const tour = {
  trail_id: "t1", name: "Feldsee-Runde", length_km: 12, ascent_m: 400, duration_h: 4, distance_km: 2,
  cover_thumb_url: "https://img/x.jpg", cover_author: "Anna", cover_license: "CC BY 4.0",
  cover_license_url: "https://cc/by", cover_page_url: "https://commons/p", results: [], deviation_text: null,
  preference: { score: 0, met: [], missing: [], avoided_hit: [] },
};

const DONE = { type: "done", usage: {}, unsupported: 0 };

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

async function ask(text = "Tour bitte") {
  await userEvent.type(screen.getByLabelText("Nachricht"), `${text}{Enter}`);
}

it("shows understood chips including 'nicht prüfbar'", async () => {
  mockStream(sse([understood, { type: "done", usage: {}, unsupported: 0 }]));
  renderChat();
  await ask();
  expect(await screen.findByText("Länge ≤ 15 km")).toBeInTheDocument();
  expect(screen.getByText(/Vorliebe: Aussicht/)).toBeInTheDocument();
  expect(screen.queryByText(/aussicht \(/)).toBeNull();
  expect(screen.getByText("nicht prüfbar: Hundefreundlich")).toBeInTheDocument();
  expect(screen.getByText("Tour bitte")).toBeInTheDocument();
});

it("shows the fallback reason above a 'Tour gefunden' line instead of cards", async () => {
  mockStream(
    sse([
      understood,
      { type: "results", cards: [tour], fallback_reason: "Keine Tour erfüllt alle Wünsche, weil …" },
      DONE,
    ]),
  );
  renderChat();
  await ask();
  const note = await screen.findByRole("note");
  const found = screen.getByText("1 Tour gefunden");
  expect(note.compareDocumentPosition(found) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Feldsee-Runde" })).toBeNull();
});

it("counts the tours of a result set, also none", async () => {
  mockStream(sse([{ type: "results", cards: [tour, { ...tour, trail_id: "t2" }], fallback_reason: null }, DONE]));
  renderChat();
  await ask();
  expect(await screen.findByText("2 Touren gefunden")).toBeInTheDocument();
  mockStream(sse([{ type: "results", cards: [], fallback_reason: null }, DONE]));
  await ask("noch eine");
  expect(await screen.findByText("Keine passende Tour gefunden.")).toBeInTheDocument();
});

it("the drawer variant is a collapsible 'Chat'", () => {
  render(
    <ChatProvider apiUrl="http://api">
      <ChatShell intro="Hi" variant="drawer" />
    </ChatProvider>,
  );
  expect(screen.getByText("Chat").closest("details")).not.toBeNull();
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
  renderChat();
  await ask();
  expect(await screen.findByText("Der Feldberg.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Quelle A" })).toHaveAttribute("href", "https://a");
  expect(screen.getByText(/Lizenz: CC BY/)).toBeInTheDocument();
  expect(screen.getByText("Entwurf")).toBeInTheDocument();
});

it("clarify options are buttons that send the answer", async () => {
  mockStream(sse([{ type: "clarify", question: "Welcher Feldberg?", options: ["Gipfel", "Gemeinde"] }, DONE]));
  renderChat();
  await ask("Feldberg");
  mockStream(sse([{ type: "token", text: "ok" }, DONE]));
  await userEvent.click(await screen.findByRole("button", { name: "Gipfel" }));
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string);
  expect(body.message).toBe("Gipfel");
  expect(body.thread_id).toMatch(/^[0-9a-f-]{36}$/);
});

it("shows a German error when the API is unreachable and keeps the input usable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
  renderChat();
  await ask();
  expect(await screen.findByRole("alert")).toHaveTextContent(/nicht erreichbar/);
  expect(screen.getByLabelText("Nachricht")).toBeEnabled();
});

it("ignores a condition without any bound and a roundtrip without value", async () => {
  const odd = {
    ...request,
    constraints: [
      { kind: "length_km", min: null, max: null, required: null },
      { kind: "roundtrip", min: null, max: null, required: null },
    ],
    preferences: [],
    unmatched: [],
  };
  mockStream(sse([{ ...understood, request: odd }, DONE]));
  renderChat();
  await ask();
  await screen.findByText("Verstanden: Tagestour, Wandern.");
  expect(screen.queryByText(/≤ 0/)).toBeNull();
  expect(screen.queryByText("kein Rundweg")).toBeNull();
});

it("shows an error when the stream ends without done", async () => {
  mockStream(sse([{ type: "token", text: "Halb" }]));
  renderChat();
  await ask();
  expect(await screen.findByRole("alert")).toHaveTextContent(/unterbrochen/);
});

it("shows the rate-limit message of a 429 answer", async () => {
  const body = sse([{ type: "error", message: "Zu viele Anfragen. Bitte warte 12 Sekunden." }]);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 429 })));
  renderChat();
  await ask();
  expect(await screen.findByRole("alert")).toHaveTextContent("Zu viele Anfragen. Bitte warte 12 Sekunden.");
});

function hangingFetch() {
  let signal: AbortSignal | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_u: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise((_res, rej) =>
        signal!.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError"))),
      );
    }),
  );
  return () => signal;
}

it("Abbrechen aborts the request, shows 'Abgebrochen.' as a plain note and frees the input", async () => {
  const getSignal = hangingFetch();
  renderChat();
  await ask();
  await userEvent.click(await screen.findByRole("button", { name: "Abbrechen" }));
  expect(getSignal()?.aborted).toBe(true);
  expect(await screen.findByText("Abgebrochen.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.getByLabelText("Nachricht")).toBeEnabled();
});

it("aborts the request on unmount", async () => {
  const getSignal = hangingFetch();
  const { unmount } = renderChat();
  await ask();
  await screen.findByRole("button", { name: "Abbrechen" });
  unmount();
  expect(getSignal()?.aborted).toBe(true);
});

it("clarify buttons are disabled while an answer is running; history is a polite live region", async () => {
  mockStream(sse([{ type: "clarify", question: "Welcher Feldberg?", options: ["Gipfel"] }, DONE]));
  renderChat();
  await ask("Feldberg");
  const btn = await screen.findByRole("button", { name: "Gipfel" });
  expect(screen.getByRole("list", { name: "Verlauf" })).toHaveAttribute("aria-live", "polite");
  hangingFetch();
  await userEvent.click(btn);
  await screen.findByRole("button", { name: "Abbrechen" });
  expect(screen.getByRole("button", { name: "Gipfel" })).toBeDisabled();
});

it("ascent chip says Hm; a single value shows its band and the value", async () => {
  const r = {
    ...request,
    constraints: [
      { kind: "ascent_m", min: null, max: 400, required: null },
      { kind: "length_km", min: 6.8, max: 9.2, required: null, approx: 8 },
    ],
  };
  mockStream(sse([{ ...understood, request: r }, DONE]));
  renderChat();
  await ask();
  expect(await screen.findByText("Höhenmeter ≤ 400 Hm")).toBeInTheDocument();
  expect(screen.getByText("Länge 6,8–9,2 km (≈ 8 km)")).toBeInTheDocument();
});

it("shows the fallback sentence once, not again at the start of the answer", async () => {
  const reason = "Keine Tour erfüllt alle Wünsche, weil jede Tour zu lang ist";
  mockStream(
    sse([
      { type: "results", cards: [tour], fallback_reason: reason },
      { type: "token", text: `${reason}.` },
      { type: "token", text: "\n\nDie Feldsee-Runde ist am nächsten dran." },
      DONE,
    ]),
  );
  renderChat();
  await ask();
  expect(await screen.findByText("Die Feldsee-Runde ist am nächsten dran.")).toBeInTheDocument();
  expect(screen.getAllByText(new RegExp(reason))).toHaveLength(1);
});

it("flags a source without name and URL instead of 'unbekannt'; same id twice is fine", async () => {
  mockStream(
    sse([
      { type: "token", text: "Antwort." },
      {
        type: "sources",
        sources: [
          { id: "osm", name: null, url: null, license: null, status: null },
          { id: "own:a", name: "A", url: "https://a/1", license: "CC BY-SA", status: null },
          { id: "own:a", name: "A", url: "https://a/2", license: "CC BY-SA", status: null },
        ],
      },
      DONE,
    ]),
  );
  const errors = vi.spyOn(console, "error").mockImplementation(() => {});
  renderChat();
  await ask();
  const list = await screen.findByRole("list", { name: "Quellen" });
  expect(list).toHaveTextContent("Quelle: osm (Angaben fehlen)");
  expect(list).not.toHaveTextContent("unbekannt");
  expect(errors).not.toHaveBeenCalled();
  errors.mockRestore();
});
