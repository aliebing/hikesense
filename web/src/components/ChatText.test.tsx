import { render, screen } from "@testing-library/react";
import ChatText from "./ChatText";

const html = (text: string) => render(<p data-testid="t"><ChatText text={text} /></p>).getByTestId("t");

test("**fett** becomes <strong>, the asterisks disappear", () => {
  const p = html("Die **Feldberg-Runde** ist 12 km lang.");
  expect(p).toHaveTextContent("Die Feldberg-Runde ist 12 km lang.");
  expect(p.querySelector("strong")).toHaveTextContent("Feldberg-Runde");
});

test("*kursiv* and _kursiv_ become <em>", () => {
  const p = html("ein *schöner* und _ruhiger_ Weg");
  expect(p).toHaveTextContent("ein schöner und ruhiger Weg");
  expect(p.querySelectorAll("em")).toHaveLength(2);
});

test("[Text](https://…) becomes a link that opens in a new tab", () => {
  html("Siehe [Wikipedia](https://de.wikipedia.org/wiki/Westweg).");
  const a = screen.getByRole("link", { name: "Wikipedia" });
  expect(a).toHaveAttribute("href", "https://de.wikipedia.org/wiki/Westweg");
  expect(a).toHaveAttribute("target", "_blank");
  expect(a).toHaveAttribute("rel", "noreferrer");
});

test("links with other schemes stay plain text (no javascript:)", () => {
  const p = html("[klick](javascript:alert(1))");
  expect(screen.queryByRole("link")).toBeNull();
  expect(p).toHaveTextContent("klick");
});

test("headings lose their # and are bold, list markers become bullets", () => {
  const p = html("### Tag 1\n- Hausach – Hornisgrinde\n* zweiter Punkt\n1. bleibt nummeriert");
  expect(p.querySelector("strong")).toHaveTextContent("Tag 1");
  expect(p.textContent).not.toContain("#");
  expect(p.textContent).toContain("• Hausach – Hornisgrinde");
  expect(p.textContent).toContain("• zweiter Punkt");
  expect(p.textContent).toContain("1. bleibt nummeriert");
});

test("an unclosed ** (while streaming) stays literal, the ? placeholder is untouched", () => {
  const p = html("Etwa ? km und **noch nicht fertig");
  expect(p).toHaveTextContent("Etwa ? km und **noch nicht fertig");
  expect(p.querySelector("strong")).toBeNull();
});

test("arithmetic asterisks are not treated as emphasis", () => {
  const p = html("3 * 15 km = 45 km");
  expect(p).toHaveTextContent("3 * 15 km = 45 km");
  expect(p.querySelector("em")).toBeNull();
});

test("raw HTML is shown as text, never interpreted", () => {
  const p = html("<b>x</b>");
  expect(p.querySelector("b")).toBeNull();
  expect(p).toHaveTextContent("<b>x</b>");
});

test("the assistant bubble in the chat renders the Markdown", async () => {
  const { default: ChatMessages } = await import("./ChatMessages");
  render(<ChatMessages items={[{ kind: "assistant", text: "Die **Hasenhorn-Runde** passt." }]} onOption={() => {}} disabled={false} />);
  expect(screen.getByText("Hasenhorn-Runde").tagName).toBe("STRONG");
  expect(screen.getByRole("list", { name: "Verlauf" })).not.toHaveTextContent("**");
});
