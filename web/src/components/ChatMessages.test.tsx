import { render, screen } from "@testing-library/react";
import ChatMessages, { splitLead, type ChatItem } from "./ChatMessages";
import type { TourCard } from "../lib/chat";

it("splitLead: the first paragraph, the rest from the blank line or the first list line", () => {
  expect(splitLead("Ich habe fünf Touren gefunden.\n\n1. A\n2. B")).toEqual(["Ich habe fünf Touren gefunden.", "1. A\n2. B"]);
  expect(splitLead("Hier sind Touren:\n1. A\n2. B")).toEqual(["Hier sind Touren:", "1. A\n2. B"]);
  expect(splitLead("Nur ein Satz.")).toEqual(["Nur ein Satz.", ""]);
  expect(splitLead("Satz.\n\n")).toEqual(["Satz.", ""]);
});

const card = (id: string) => ({ trail_id: id, name: id, results: [], preference: { score: 0, met: [], missing: [], avoided_hit: [] } }) as unknown as TourCard;
const answer = "Ich habe zwei Touren gefunden.\n\n1. **A** – 10 km\n2. **B** – 12 km";
const turn = (cards: TourCard[]): ChatItem[] => [
  { kind: "user", text: "Rundweg" },
  { kind: "results", cards, fallback: null, runWithoutPace: false, labels: {} },
  { kind: "assistant", text: answer },
];

it("next to 2+ cards the answer shows only its lead; the list opens on demand", () => {
  render(<ChatMessages items={turn([card("a"), card("b")])} onOption={() => {}} disabled={false} />);
  expect(screen.getByText("Ich habe zwei Touren gefunden.")).toBeVisible();
  const more = screen.getByText("Ganze Antwort zeigen");
  expect(more.closest("details")).not.toHaveAttribute("open");
});

it("with a single card the answer stays in full", () => {
  render(<ChatMessages items={turn([card("a")])} onOption={() => {}} disabled={false} />);
  expect(screen.queryByText("Ganze Antwort zeigen")).toBeNull();
});

it("older turns are dimmed, a new turn starts with a separator", () => {
  const items: ChatItem[] = [...turn([card("a")]), { kind: "user", text: "kürzer" }];
  const { container } = render(<ChatMessages items={items} onOption={() => {}} disabled={false} />);
  const lis = container.querySelectorAll("li[data-turn]");
  expect(lis).toHaveLength(2);
  expect(lis[0]).toHaveClass("opacity-80");
  expect(lis[1]).toHaveClass("border-t");
  expect(lis[1]).not.toHaveClass("opacity-80");
});

it("more than 8 options: 7 shown and a button for the rest", async () => {
  const options = Array.from({ length: 10 }, (_, i) => `Ort ${i + 1}`);
  render(<ChatMessages items={[{ kind: "clarify", question: "Wo?", options }]} onOption={() => {}} disabled={false} />);
  expect(screen.getAllByRole("button")).toHaveLength(8);
  screen.getByRole("button", { name: "+ 3 weitere" }).click();
  expect(await screen.findByRole("button", { name: "Ort 10" })).toBeInTheDocument();
});
