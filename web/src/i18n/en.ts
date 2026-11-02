/** English catalog (default language). Nested by area; texts with placeholders are functions. */
export const en = {
  common: {
    flags: { group: "Language" },
  },
  home: {},
  chat: {},
  results: {},
  tour: {},
  plan: {},
  account: {},
  admin: {},
  errors: {},
} as const;

/** Same shape as `en`, with literal strings widened so other languages can differ in text. */
type Widen<T> = T extends string ? string : T extends (...a: infer A) => infer R ? (...a: A) => Widen<R> : { -readonly [K in keyof T]: Widen<T[K]> };
export type Messages = Widen<typeof en>;
