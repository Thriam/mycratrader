import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "mycratrader — NSE/BSE quant research",
  description:
    "Multi-algorithm stock prediction for NSE & BSE with walk-forward backtesting and free LLM consensus.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
