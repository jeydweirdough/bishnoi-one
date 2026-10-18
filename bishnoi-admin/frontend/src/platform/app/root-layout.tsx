import type { Metadata, Viewport } from "next";
import { Addresses } from "./addresses";
import { Poppins } from "next/font/google";
import type { ReactNode } from "react";
import { Toaster } from "sonner";
import icon from "@/src/components/assets/icon.png";
import { thisAppLabel } from "../lib/apps";
import { APP_NAME } from "../lib/labels";

// Poppins isn't a variable font, so each weight the screens use is named.
const poppins = Poppins({ variable: "--font-poppins", subsets: ["latin"], weight: ["400", "500", "600", "700"] });

// The product and which app this is, so the tab reads "Bishnoi One Admin".
const NAME = thisAppLabel() ? `${APP_NAME} ${thisAppLabel()}` : APP_NAME;

/** What every app calls itself, unless it says otherwise. */
export const metadata: Metadata = {
  title: { default: NAME, template: `%s · ${NAME}` },
  // Square, so the browser doesn't squash the tall logo into the tab.
  icons: { icon: icon.src, apple: icon.src },
  description: "Customers, calls, visits and follow-ups for every division and team.",
};

export const viewport: Viewport = { themeColor: "#eceef2" };

/**
 * The frame round every Bishnoi One app — the shell and each module alike.
 *
 * Deliberately takes plain children rather than Next's `LayoutProps<"/">`: that
 * type is built from one app's routes, and this is worn by all of them.
 */
export function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${poppins.variable} antialiased`}>
      <body className="min-h-dvh font-sans">
        <Addresses />
        {children}
        <Toaster
          position="top-center"
          toastOptions={{
            classNames: {
              toast: "!rounded-[12px] !border-0 !shadow-overlay !font-sans !text-sm !text-ink",
              description: "!text-ink-2",
            },
          }}
        />
      </body>
    </html>
  );
}
