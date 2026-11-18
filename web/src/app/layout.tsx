import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AnalysisProvider } from "@/state/analysis-store";
import { AppShell } from "@/components/shell/app-shell";

export const metadata: Metadata = {
  title: { default: "Therma Search AI", template: "%s · Therma Search AI" },
  description: "Termal İHA görüntülerinde insan tespiti için arama-kurtarma karar destek platformu (MVP iskeleti).",
};

export const viewport: Viewport = { themeColor: "#060a13", colorScheme: "dark" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="tr">
      <body>
        <AnalysisProvider>
          <AppShell>{children}</AppShell>
        </AnalysisProvider>
      </body>
    </html>
  );
}
