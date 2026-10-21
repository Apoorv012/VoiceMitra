import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans, Noto_Sans_Devanagari } from "next/font/google";
import "./globals.css";
import { PwaRegister } from "@/components/PwaRegister";

const latin = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-latin", display: "swap" });
const devanagari = Noto_Sans_Devanagari({ subsets: ["devanagari"], variable: "--font-deva", display: "swap" });

export const metadata: Metadata = {
  title: { default: "VoiceMitra", template: "%s · VoiceMitra" },
  description: "Your medicine companion: gentle daily check-ins by voice, with your doctor one call away.",
  applicationName: "VoiceMitra",
  appleWebApp: { capable: true, title: "VoiceMitra", statusBarStyle: "default" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#e9ece7" },
    { media: "(prefers-color-scheme: dark)", color: "#0c110c" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${latin.variable} ${devanagari.variable}`}>
      <body>
        {children}
        <PwaRegister />
      </body>
    </html>
  );
}
