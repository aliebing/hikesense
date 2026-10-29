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
