import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { ReactNode } from "react";
import { Toaster } from "@/src/components/ui/sonner";
import { TooltipProvider } from "@/src/components/ui/tooltip";
import { ThemeProvider } from "next-themes";
import { APP_NAME } from "../lib/labels";

// Geist, as Studio Admin uses it (shadcn/ui, 2026-11-19), from the geist package: kept with the app, so a
// server whose internet is down still builds.
const fontVars = `${GeistSans.variable} ${GeistMono.variable}`;

/** What every Bishnoi One app calls itself, unless it says otherwise. */
export const metadata: Metadata = {
  title: { default: APP_NAME, template: `%s · ${APP_NAME}` },
  description: "Customers, quotes, activities and products for every team.",
};

export const viewport: Viewport = { themeColor: "#ffffff" };

/**
 * The frame round every Bishnoi One app — the shell and each module alike.
 *
 * Deliberately takes plain children rather than Next's `LayoutProps<"/">`: that
 * type is built from one app's routes, and this is worn by all of them.
 */
export function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${fontVars} antialiased`} suppressHydrationWarning>
      <body className="min-h-dvh font-sans">
        {/* Light, dark or as the computer is set (Studio Admin's switch, src/platform/shell/theme-switch.tsx); light until chosen. */}
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
          <TooltipProvider>{children}</TooltipProvider>
          <Toaster position="top-center" duration={4000} />
        </ThemeProvider>
      </body>
    </html>
  );
}
