import type { Metadata, Viewport } from "next";
import { Montserrat } from "next/font/google";
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
    icons: {
      icon: [{ url: "/favicon.ico", sizes: "any" }, { url: "/icons/icon.svg", type: "image/svg+xml" }],
      apple: "/icons/apple-touch-icon.png",
    },
  };
}

// the brand face (wordmark, hero, tagline); body text stays on the system sans
const brand = Montserrat({ subsets: ["latin"], weight: ["500", "600", "800"], variable: "--font-montserrat", display: "swap" });

export const viewport: Viewport = { themeColor: "#2f5d3a" };

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const locale = await getServerLocale();
  return (
    <html lang={locale} className={brand.variable}>
      <body className="antialiased"><LocaleProvider initialLocale={locale}><ChatProvider>{children}</ChatProvider></LocaleProvider><ServiceWorker /></body>
    </html>
  );
}
