import { render } from "@testing-library/react";
import HomeStage from "./HomeStage";
import { initialState } from "../lib/chatState";

// Before the tab's saved conversation is read, the page cannot know whether it shows the start
// view or results: the start photo and hero must not flash, they fade in once it is known.
const chat = { state: initialState("th"), busy: false, hydrated: false, send: vi.fn(), abort: vi.fn(), reset: vi.fn() };
vi.mock("./ChatProvider", () => ({ useChat: () => chat }));
vi.mock("./ChatShell", () => ({ default: () => <p>chat</p> }));

beforeEach(() => {
  chat.hydrated = false;
});

it("before hydration the start photo and hero are invisible", () => {
  const { container } = render(<HomeStage />);
  expect(container.querySelector("[data-hero-backdrop]")).toHaveClass("opacity-0");
  expect(container.querySelector("[data-hero-content]")).toHaveClass("opacity-0");
});

it("after hydration without results they fade in", () => {
  chat.hydrated = true;
  const { container } = render(<HomeStage />);
  expect(container.querySelector("[data-hero-backdrop]")).not.toHaveClass("opacity-0");
  expect(container.querySelector("[data-hero-content]")).not.toHaveClass("opacity-0");
  expect(container.querySelector("[data-hero-backdrop]")).toHaveClass("transition-opacity");
});
