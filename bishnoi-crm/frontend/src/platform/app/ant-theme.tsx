"use client";

import { AntdRegistry } from "@ant-design/nextjs-registry";
import { ConfigProvider, theme } from "antd";
import type { ReactNode } from "react";

/**
 * Ant Design for every screen: its components, in Poppins, with Ant's own
 * blue and corners. The registry writes Ant's styles into the page on the
 * server, so nothing flashes unstyled. The design tokens in globals.css carry
 * the same palette for what's still drawn with Tailwind.
 */
export const ANT_THEME = {
  algorithm: theme.defaultAlgorithm,
  token: {
    fontFamily: "var(--font-poppins), ui-sans-serif, system-ui, sans-serif",
    colorPrimary: "#1677ff",
    colorSuccess: "#52c41a",
    colorWarning: "#faad14",
    colorError: "#ff4d4f",
    borderRadius: 6,
    colorBgLayout: "#f5f5f5",
    colorText: "#1f1f1f",
    colorLink: "#1f1f1f",
    colorLinkHover: "#000000",
  },
  components: {
    // Text is near black, never blue: blue is for primary buttons and focus only.
    Segmented: { itemSelectedColor: "#1f1f1f" },
  },
};

export function AntTheme({ children }: { children: ReactNode }) {
  return (
    <AntdRegistry>
      <ConfigProvider theme={ANT_THEME}>
        {children}
      </ConfigProvider>
    </AntdRegistry>
  );
}
