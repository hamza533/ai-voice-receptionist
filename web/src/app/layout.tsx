import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: {
    default: "Receptly – AI receptionist for Luma Hair Studio",
    template: "%s · Receptly",
  },
  description:
    "Never miss a call: an AI receptionist that answers, books appointments in your calendar and hands off to a human when needed.",
};

export const viewport: Viewport = { themeColor: "#00685b" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full">
        {children}
        <Toaster position="top-right" richColors closeButton />
      </body>
    </html>
  );
}
