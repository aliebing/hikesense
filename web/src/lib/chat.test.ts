import { chatError, parseSse, streamChat, type ChatEvent } from "./chat";

const ev = (type: string, extra: object = {}) => `event: ${type}\ndata: ${JSON.stringify({ type, ...extra })}\n\n`;

it("parses events split across chunks", () => {
  const whole = ev("token", { text: "Hallo" }) + ev("done", { usage: {}, unsupported: 0 });
  const cut = 25;
  const a = parseSse(whole.slice(0, cut), "");
  expect(a.events).toEqual([]);
  const b = parseSse(whole.slice(cut), a.rest);
  expect(b.events.map((e) => e.type)).toEqual(["token", "done"]);
  expect(b.rest).toBe("");
});

it("handles CRLF and ignores comments", () => {
  const r = parseSse(`: ping\r\n\r\nevent: token\r\ndata: {"type":"token","text":"x"}\r\n\r\n`, "");
  expect(r.events).toEqual([{ type: "token", text: "x" }]);
});

it("shows a German error event when the API is unreachable", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e), undefined, null, "de");
  expect(got).toHaveLength(1);
  expect(got[0]).toMatchObject({ type: "error", message: expect.stringContaining("nicht erreichbar") });
  vi.unstubAllGlobals();
});

it("keeps a CRLF split across chunks inside one event", () => {
  const a = parseSse('event: token\r\ndata: {"type":"token",\r', "");
  expect(a.events).toEqual([]);
  const b = parseSse('\ndata: "text":"x"}\r\n\r\n', a.rest);
  expect(b.events).toEqual([{ type: "token", text: "x" }]);
});

function streamOf(...chunks: string[]) {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      chunks.forEach((x) => c.enqueue(enc.encode(x)));
      c.close();
    },
  });
}

it("parses a final event without trailing blank line", async () => {
  const body = `event: done\ndata: {"type":"done","usage":{},"unsupported":0}`;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(streamOf(body), { status: 200 })));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e), undefined, null, "de");
  expect(got.map((e) => e.type)).toEqual(["done"]);
  vi.unstubAllGlobals();
});

it("reports an error when the stream ends without done", async () => {
  const body = `event: token\ndata: {"type":"token","text":"a"}\n\n`;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(streamOf(body), { status: 200 })));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e), undefined, null, "de");
  expect(got.map((e) => e.type)).toEqual(["token", "error"]);
  expect(got[1]).toMatchObject({ message: expect.stringContaining("unterbrochen") });
  vi.unstubAllGlobals();
});

it("passes through the 429 error event without a second error", async () => {
  const body = `event: error\ndata: {"type":"error","message":"Zu viele Anfragen. Bitte warte 30 Sekunden."}\n\n`;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(streamOf(body), { status: 429 })));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e), undefined, null, "de");
  expect(got).toEqual([{ type: "error", message: "Zu viele Anfragen. Bitte warte 30 Sekunden." }]);
  vi.unstubAllGlobals();
});

it("is silent when aborted", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));
  const got: ChatEvent[] = [];
  const ctrl = new AbortController();
  ctrl.abort();
  await streamChat("http://x", "t", "hi", (e) => got.push(e), ctrl.signal, null, "de");
  expect(got).toEqual([]);
  vi.unstubAllGlobals();
});

it("a rejected request (4xx without events) gets its own message, not 'nicht erreichbar'", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response('{"detail":[]}', { status: 422, headers: { "Content-Type": "application/json" } })),
  );
  const got: ChatEvent[] = [];
  await streamChat("http://api", "t", "x", (e) => got.push(e), undefined, null, "de");
  expect(got).toEqual([{ type: "error", message: chatError("rejected", "de") }]);
  vi.unstubAllGlobals();
});

it("sends the language in the request body", async () => {
  const fetchMock = vi.fn().mockRejectedValue(new TypeError("x"));
  vi.stubGlobal("fetch", fetchMock);
  await streamChat("http://x", "t", "hi", () => {}, undefined, null, "en");
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ thread_id: "t", message: "hi", lang: "en" });
  vi.unstubAllGlobals();
});

it("web error texts follow the language, in both languages", async () => {
  const { isAuthUnavailable } = await import("./chat");
  expect(chatError("unreachable", "en")).toBe("The planning service is not available right now. Please try again shortly.");
  expect(chatError("rejected", "de")).toBe("Die Nachricht konnte nicht verarbeitet werden. Bitte formuliere sie neu oder kürzer.");
  expect(isAuthUnavailable(chatError("authUnavailable", "en"))).toBe(true);
  expect(isAuthUnavailable(chatError("authUnavailable", "de"))).toBe(true);
  expect(isAuthUnavailable("anything else")).toBe(false);
});

it("sends no authorization header without a token", async () => {
  const fetchMock = vi.fn().mockRejectedValue(new TypeError("x"));
  vi.stubGlobal("fetch", fetchMock);
  await streamChat("http://x", "t", "hi", () => {}, undefined, null, "de");
  expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  vi.unstubAllGlobals();
});

it("a 403 account_blocked becomes a blocked event", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":"account_blocked"}', { status: 403 })));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e), undefined, "tok", "de");
  expect(got).toEqual([{ type: "blocked" }]);
  vi.unstubAllGlobals();
});

it("keeps the code of a guest-limit error event", async () => {
  const body = `event: error\ndata: {"type":"error","message":"aufgebraucht","code":"guest_limit"}\n\n`;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(streamOf(body), { status: 429 })));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e), undefined, null, "de");
  expect(got).toEqual([{ type: "error", message: "aufgebraucht", code: "guest_limit" }]);
  vi.unstubAllGlobals();
});
