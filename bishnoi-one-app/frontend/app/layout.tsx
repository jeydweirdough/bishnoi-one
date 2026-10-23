// The frame is core's, so every Bishnoi One app looks and behaves the same.
import type { ReactNode } from "react";
import { RootLayout } from "@/src/platform/app/root-layout";
import "./globals.css";

export { metadata, viewport } from "@/src/platform/app/root-layout";

export default function Layout({ children }: { children: ReactNode }) {
  return <RootLayout>{children}</RootLayout>;
}
