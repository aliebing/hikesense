import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ChatProvider } from "../components/ChatProvider";
import ServiceWorker from "../components/ServiceWorker";

export const metadata: Metadata = {
  title: "Hike all about – Wandern im Schwarzwald",
  description: "Wanderungen im Schwarzwald im Gespräch planen: Fernweg-Etappen (Westweg, Mittelweg, Ostweg) und Tagestouren.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
};

export const viewport: Viewport = { themeColor: "#2f5d3a" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de">
      <body className="antialiased"><ChatProvider>{children}</ChatProvider><ServiceWorker /></body>
    </html>
  );
}
