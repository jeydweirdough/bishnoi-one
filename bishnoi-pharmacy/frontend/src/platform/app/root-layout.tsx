import type { Metadata, Viewport } from "next";
import { Addresses } from "./addresses";
import { Poppins } from "next/font/google";
import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { ToastIcon } from "../ui/toast-icon";
import { APP_NAME } from "../lib/labels";

// Poppins has no variable version, so each weight in use is loaded by name.
const poppins = Poppins({ variable: "--font-poppins", subsets: ["latin"], weight: ["400", "500", "600", "700"] });

/** What every Bishnoi One app calls itself, unless it says otherwise. */
export const metadata: Metadata = {
  title: { default: APP_NAME, template: `%s · ${APP_NAME}` },
  description: "Customers, quotes, activities and products for every team.",
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
          // The UI kit's light toasts (decided 2026-10-22): white, a thin line, its round icon, closing after 4 seconds.
          duration={4000}
          icons={{
            success: <ToastIcon tone="ok" />,
            info: <ToastIcon tone="info" />,
            warning: <ToastIcon tone="warn" />,
            error: <ToastIcon tone="bad" />,
          }}
          toastOptions={{
            classNames: {
              toast: "!rounded-[12px] !border !border-rule !bg-sheet !py-2.5 !pr-3 !pl-3.5 !shadow-[0_10px_30px_rgba(20,20,20,0.12)] !font-sans !text-[0.84375rem] !text-ink",
              title: "!font-medium",
              description: "!text-ink-2",
              actionButton: "!bg-transparent !px-1 !font-semibold !text-ink !underline !underline-offset-[3px]",
              cancelButton: "!bg-transparent !text-ink-2",
            },
          }}
        />
      </body>
    </html>
  );
}
