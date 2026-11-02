import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ChatProvider } from "../components/ChatProvider";
import { LocaleProvider } from "../i18n";
import { getServerLocale } from "../i18n/server";
import ServiceWorker from "../components/ServiceWorker";

export const metadata: Metadata = {
  title: "Hike all about – Wandern im Schwarzwald, am Bodensee und im Pfälzerwald",
  description: "Wanderungen im Schwarzwald, am Bodensee und im Pfälzerwald im Gespräch planen: Fernweg-Etappen (z. B. Westweg, Pfälzer Weinsteig, SeeGang) und Tagestouren.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
};

export const viewport: Viewport = { themeColor: "#2f5d3a" };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const locale = await getServerLocale();
  return (
    <html lang={locale}>
      <body className="antialiased"><LocaleProvider initialLocale={locale}><ChatProvider>{children}</ChatProvider></LocaleProvider><ServiceWorker /></body>
    </html>
  );
}
