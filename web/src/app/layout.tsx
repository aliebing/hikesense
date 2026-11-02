import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ChatProvider } from "../components/ChatProvider";
import { LocaleProvider } from "../i18n";
import { messagesFor } from "../i18n/locale";
import { getServerLocale } from "../i18n/server";
import ServiceWorker from "../components/ServiceWorker";

/** Title and description follow the visitor's language (cookie); English without a choice. */
export async function generateMetadata(): Promise<Metadata> {
  const t = messagesFor(await getServerLocale()).frame;
  return {
    title: t.metaTitle,
    description: t.metaDescription,
    manifest: "/manifest.webmanifest",
    icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
  };
}

export const viewport: Viewport = { themeColor: "#2f5d3a" };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const locale = await getServerLocale();
  return (
    <html lang={locale}>
      <body className="antialiased"><LocaleProvider initialLocale={locale}><ChatProvider>{children}</ChatProvider></LocaleProvider><ServiceWorker /></body>
    </html>
  );
}
