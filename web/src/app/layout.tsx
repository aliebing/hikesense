import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hike all about – Wandern im Schwarzwald",
  description: "Wanderungen im Schwarzwald im Gespräch planen: Westweg-Etappen und Tagestouren.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de">
      <body className="antialiased">{children}</body>
    </html>
  );
}
