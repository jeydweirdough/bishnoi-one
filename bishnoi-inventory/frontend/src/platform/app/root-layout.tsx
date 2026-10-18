import type { Metadata, Viewport } from "next";
import { Poppins } from "next/font/google";
import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { APP_NAME } from "../lib/labels";
import { Addresses } from "./addresses";
import { AntTheme } from "./ant-theme";

// Poppins has no variable version, so each weight in use is loaded by name.
const poppins = Poppins({ variable: "--font-poppins", subsets: ["latin"], weight: ["400", "500", "600", "700"] });

/** What every Bishnoi One app calls itself, unless it says otherwise. */
export const metadata: Metadata = {
  title: { default: APP_NAME, template: `%s · ${APP_NAME}` },
  description: "Customers, quotes, activities and products for every team.",
};

export const viewport: Viewport = { themeColor: "#f5f5f5" };

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
        <AntTheme>{children}</AntTheme>
        <Toaster
          position="top-center"
          toastOptions={{
            classNames: {
              toast: "!rounded-xl !border-0 !shadow-overlay !font-sans !text-sm !text-ink",
              description: "!text-ink-2",
            },
          }}
        />
      </body>
    </html>
  );
}
