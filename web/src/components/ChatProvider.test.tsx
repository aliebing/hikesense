import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
const auth = vi.hoisted(() => ({ signedOut: null as null | (() => void) }));
vi.mock("../lib/auth", () => ({
  getAccessToken: async () => null,
  onSignedOut: (cb: () => void) => {
    auth.signedOut = cb;
    return () => {
      auth.signedOut = null;
    };
  },
}));

import { ChatProvider, useChat } from "./ChatProvider";
import { initialState, saveState, STORAGE_KEY } from "../lib/chatState";

const sse = (events: object[]) =>
  events.map((e) => `event: ${(e as { type: string }).type}\ndata: ${JSON.stringify(e)}\n\n`).join("");

function mockStream(body: string) {
  const stream = new ReadableStream({
    start(c) {
      c.enqueue(new TextEncoder().encode(body));
      c.close();
    },
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream, { status: 200 })));
}

const DONE = { type: "done", usage: {}, unsupported: 0 };
const tour = { trail_id: "t1", name: "Feldsee-Runde" };

function Probe({ name }: { name: string }) {
  const { state, busy, send, abort } = useChat();
  return (
    <div data-testid={name}>
      <span>{`${name}:items=${state.items.length}`}</span>
      <span>{`${name}:last=${state.last?.cards.length ?? "none"}`}</span>
      <span>{`${name}:busy=${busy}`}</span>
      <span>{`${name}:thread=${state.threadId}`}</span>
      <button onClick={() => void send("Hallo")}>{`${name}-send`}</button>
      <button onClick={abort}>{`${name}-abort`}</button>
    </div>
  );
}

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

it("shares one conversation", async () => {
  mockStream(sse([{ type: "token", text: "Hi" }, DONE]));
  render(
    <ChatProvider apiUrl="http://api">
      <Probe name="a" />
      <Probe name="b" />
    </ChatProvider>,
  );
  await userEvent.click(screen.getByText("a-send"));
  expect(await screen.findByText("b:items=2")).toBeInTheDocument();
  expect(screen.getByText("a:items=2")).toBeInTheDocument();
});

it("restores from sessionStorage", async () => {
  const s = {
    ...initialState("saved-thread"),
    last: { cards: [tour as never], fallback: null, runWithoutPace: false, labels: {}, request: null },
  };
  saveState(sessionStorage, s);
  render(
    <ChatProvider>
      <Probe name="a" />
    </ChatProvider>,
  );
  expect(await screen.findByText("a:last=1")).toBeInTheDocument();
  expect(screen.getByText("a:thread=saved-thread")).toBeInTheDocument();
});

it("busy is never restored", async () => {
  saveState(sessionStorage, initialState("x"));
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...JSON.parse(sessionStorage.getItem(STORAGE_KEY)!), busy: true }));
  render(
    <ChatProvider>
      <Probe name="a" />
    </ChatProvider>,
  );
  await screen.findByText("a:thread=x");
  expect(screen.getByText("a:busy=false")).toBeInTheDocument();
});

it("saves after each change", async () => {
  mockStream(sse([{ type: "token", text: "Hi" }, DONE]));
  render(
    <ChatProvider apiUrl="http://api">
      <Probe name="a" />
    </ChatProvider>,
  );
  await userEvent.click(screen.getByText("a-send"));
  await screen.findByText("a:items=2");
  expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).items).toHaveLength(2);
});

it('abort adds the notice "Abgebrochen."', async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((_u: string, init: RequestInit) => {
      const signal = init.signal as AbortSignal;
      return new Promise((_r, rej) => signal.addEventListener("abort", () => rej(new DOMException("a", "AbortError"))));
    }),
  );
  render(
    <ChatProvider apiUrl="http://api">
      <Probe name="a" />
    </ChatProvider>,
  );
  await userEvent.click(screen.getByText("a-send"));
  await screen.findByText("a:busy=true");
  await act(async () => screen.getByText("a-abort").click());
  expect(await screen.findByText("a:busy=false")).toBeInTheDocument();
  expect(JSON.parse(sessionStorage.getItem(STORAGE_KEY)!).items.at(-1)).toEqual({ kind: "notice", text: "Abgebrochen." });
});

it("posts to the same-origin /api/chat by default (proxied by Next)", async () => {
  mockStream(sse([DONE]));
  render(
    <ChatProvider>
      <Probe name="a" />
    </ChatProvider>,
  );
  await userEvent.click(screen.getByText("a-send"));
  await screen.findByText("a:busy=false");
  expect(vi.mocked(fetch).mock.calls[0][0]).toBe("/api/chat");
});

it("sign-out starts a fresh conversation and clears the stored one (shared device)", async () => {
  mockStream(sse([{ type: "token", text: "Hi" }, DONE]));
  saveState(sessionStorage, initialState("old-thread"));
  render(
    <ChatProvider apiUrl="http://api">
      <Probe name="a" />
    </ChatProvider>,
  );
  await screen.findByText("a:thread=old-thread");
  await userEvent.click(screen.getByText("a-send"));
  await screen.findByText("a:items=2");
  await act(async () => auth.signedOut?.());
  expect(screen.getByText("a:items=0")).toBeInTheDocument();
  expect(screen.queryByText("a:thread=old-thread")).toBeNull();
  const stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? "null");
  expect(stored === null || (stored.items.length === 0 && stored.threadId !== "old-thread")).toBe(true);
});

it("a stream still running at sign-out does not write into the fresh conversation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((_u: string, init: RequestInit) => {
      const signal = init.signal as AbortSignal;
      return new Promise((_r, rej) => signal.addEventListener("abort", () => rej(new DOMException("a", "AbortError"))));
    }),
  );
  render(
    <ChatProvider apiUrl="http://api">
      <Probe name="a" />
    </ChatProvider>,
  );
  await userEvent.click(screen.getByText("a-send"));
  await screen.findByText("a:busy=true");
  await act(async () => auth.signedOut?.());
  expect(await screen.findByText("a:busy=false")).toBeInTheDocument();
  expect(screen.getByText("a:items=0")).toBeInTheDocument(); // no „Abgebrochen.“ in the new chat
});
