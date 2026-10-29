import { parseSse, streamChat, type ChatEvent } from "./chat";

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
  await streamChat("http://x", "t", "hi", (e) => got.push(e));
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
  await streamChat("http://x", "t", "hi", (e) => got.push(e));
  expect(got.map((e) => e.type)).toEqual(["done"]);
  vi.unstubAllGlobals();
});

it("reports an error when the stream ends without done", async () => {
  const body = `event: token\ndata: {"type":"token","text":"a"}\n\n`;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(streamOf(body), { status: 200 })));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e));
  expect(got.map((e) => e.type)).toEqual(["token", "error"]);
  expect(got[1]).toMatchObject({ message: expect.stringContaining("unterbrochen") });
  vi.unstubAllGlobals();
});

it("passes through the 429 error event without a second error", async () => {
  const body = `event: error\ndata: {"type":"error","message":"Zu viele Anfragen. Bitte warte 30 Sekunden."}\n\n`;
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(streamOf(body), { status: 429 })));
  const got: ChatEvent[] = [];
  await streamChat("http://x", "t", "hi", (e) => got.push(e));
  expect(got).toEqual([{ type: "error", message: "Zu viele Anfragen. Bitte warte 30 Sekunden." }]);
  vi.unstubAllGlobals();
});

it("is silent when aborted", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));
  const got: ChatEvent[] = [];
  const ctrl = new AbortController();
  ctrl.abort();
  await streamChat("http://x", "t", "hi", (e) => got.push(e), ctrl.signal);
  expect(got).toEqual([]);
  vi.unstubAllGlobals();
});
