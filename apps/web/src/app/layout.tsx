import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VREDA.ai — Scientific Lab Orchestrator",
  description:
    "The Scientific Operating System. Upload research papers, get AI-powered analysis, and automate the scientific method from ideation to verification.",
  keywords: [
    "AI research",
    "scientific automation",
    "research assistant",
    "paper analysis",
    "VREDA",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin=""
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
