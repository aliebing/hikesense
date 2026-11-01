import { expect, it } from "vitest";
import { fromChat } from "./von";

it("only chat and the old vorschlaege count as coming from the chat", () => {
  expect(fromChat("chat")).toBe(true);
  expect(fromChat("vorschlaege")).toBe(true);
  expect(fromChat(undefined)).toBe(false);
  expect(fromChat("x")).toBe(false);
  expect(fromChat(["chat"])).toBe(false);
});
