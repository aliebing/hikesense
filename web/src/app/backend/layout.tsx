import type { Metadata } from "next";

// Not linked anywhere in the app; search engines should not list it either.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function BackendLayout({ children }: { children: React.ReactNode }) {
  return children;
}
