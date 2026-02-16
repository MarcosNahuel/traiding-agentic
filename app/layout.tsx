import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trading Agentic",
  description: "AI-powered trading research and strategy agent",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="bg-zinc-950 text-zinc-100 antialiased">{children}</body>
    </html>
  );
}
