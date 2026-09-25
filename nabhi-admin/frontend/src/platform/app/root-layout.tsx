import type { Metadata, Viewport } from "next";
import { Public_Sans } from "next/font/google";
import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { APP_NAME } from "../lib/labels";

const publicSans = Public_Sans({ variable: "--font-public-sans", subsets: ["latin"] });

/** What every Orbit app calls itself, unless it says otherwise. */
export const metadata: Metadata = {
  title: { default: APP_NAME, template: `%s · ${APP_NAME}` },
  description: "Customers, calls, visits and follow-ups for every division and team.",
};

export const viewport: Viewport = { themeColor: "#eceef2" };

/**
 * The frame round every Orbit app — the shell and each module alike.
 *
 * Deliberately takes plain children rather than Next's `LayoutProps<"/">`: that
 * type is built from one app's routes, and this is worn by all of them.
 */
export function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${publicSans.variable} antialiased`}>
      <body className="min-h-dvh font-sans">
        {children}
        <Toaster
          position="top-center"
          toastOptions={{
            classNames: {
              toast: "!rounded-[3px] !border-0 !shadow-overlay !font-sans !text-sm !text-ink",
              description: "!text-ink-2",
            },
          }}
        />
      </body>
    </html>
  );
}
