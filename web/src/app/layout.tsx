import type { Metadata } from "next";
import "./globals.css";
import { ChatProvider } from "../components/ChatProvider";

export const metadata: Metadata = {
  title: "Hike all about – Wandern im Schwarzwald",
  description: "Wanderungen im Schwarzwald im Gespräch planen: Westweg-Etappen und Tagestouren.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de">
      <body className="antialiased"><ChatProvider>{children}</ChatProvider></body>
    </html>
  );
}
