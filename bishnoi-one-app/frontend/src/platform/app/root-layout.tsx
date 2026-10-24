import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import { Toaster } from "sonner";
import { ToastIcon } from "../ui/toast-icon";
import { APP_NAME } from "../lib/labels";
import { AntTheme } from "./ant-theme";

// Poppins, kept with the app (src/platform/fonts, the Latin set of each weight
// in use; SIL Open Font License): a build never has to reach Google Fonts, so
// a server whose internet is down still builds (decided 2026-10-23).
const poppins = localFont({
  variable: "--font-poppins",
  display: "swap",
  src: [
    { path: "../fonts/poppins-400.woff2", weight: "400", style: "normal" },
    { path: "../fonts/poppins-500.woff2", weight: "500", style: "normal" },
    { path: "../fonts/poppins-600.woff2", weight: "600", style: "normal" },
    { path: "../fonts/poppins-700.woff2", weight: "700", style: "normal" },
  ],
});

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
        <AntTheme>{children}</AntTheme>
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
