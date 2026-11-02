import { cookies } from "next/headers";
import { COOKIE_NAME, isLocale, type Locale } from "./locale";

/** Language chosen by the visitor (cookie), English when missing or unknown. Server components only. */
export async function getServerLocale(): Promise<Locale> {
  const v = (await cookies()).get(COOKIE_NAME)?.value;
  return isLocale(v) ? v : "en";
}
