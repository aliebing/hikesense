/** `?von=chat` on a trail link: the visitor came from a chat search. The old value `vorschlaege` counts the same. */
export function fromChat(von: string | string[] | undefined): boolean {
  return von === "chat" || von === "vorschlaege";
}
