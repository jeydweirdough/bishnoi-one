"use client";

import { AntdRegistry } from "@ant-design/nextjs-registry";
import { ConfigProvider, theme } from "antd";
import type { ReactNode } from "react";

/**
 * Ant Design for every screen, in the sign-in page's look (Desktop:
 * bishnoi-one-crm-components.html): ink for what you press, sage for progress
 * and what's done, mint for hover and what's selected; fields and buttons as
 * pills, cards and dialogs with soft corners. The registry writes Ant's styles
 * into the page on the server, so nothing flashes unstyled. The design tokens
 * in globals.css carry the same palette for what's drawn with Tailwind.
 */
const INK = "#141414";
const MINT = "#f1f7ee";
const SAGE = "#a8d69b";

export const ANT_THEME = {
  algorithm: theme.defaultAlgorithm,
  token: {
    fontFamily: "var(--font-poppins), ui-sans-serif, system-ui, sans-serif",
    colorPrimary: INK,
    // The light tints Ant makes from the main colour (picked rows, soft buttons): mint, not shades of ink.
    colorPrimaryBg: MINT,
    colorPrimaryBgHover: "#e3eedf",
    colorInfo: "#1f4f8a",
    colorSuccess: "#3f6f35",
    colorWarning: "#b07400",
    colorError: "#b42318",
    colorText: INK,
    colorTextSecondary: "#3b3b3b",
    colorTextTertiary: "#6a6a6a",
    colorBorder: "#8a8a8a",
    colorBorderSecondary: "#ececea",
    colorBgLayout: "#fafaf8",
    colorLink: INK,
    colorLinkHover: "#000000",
    controlItemBgActive: MINT,
    // Picked and pointed at, at once (the only option in a list): a deeper mint, never the ink it falls back to.
    controlItemBgActiveHover: "#e3eedf",
    controlItemBgHover: "#f4f4f2",
    controlOutline: "rgba(127, 176, 112, 0.35)",
    borderRadius: 20,
    borderRadiusLG: 22,
    borderRadiusSM: 12,
    borderRadiusXS: 8,
    controlHeight: 36,
    controlHeightSM: 28,
    controlHeightLG: 44,
    boxShadow: "0 10px 30px rgba(20, 20, 20, 0.12)",
    boxShadowSecondary: "0 10px 30px rgba(20, 20, 20, 0.12)",
  },
  components: {
    // Buttons in the UI kit's shape (decided 2026-10-22): 40 px tall with room at the
    // sides, small 34, large 48; a light outline that greys on hover; text fields stay 36.
    Button: {
      controlHeight: 40, controlHeightSM: 34, controlHeightLG: 48,
      paddingInline: 18, paddingInlineSM: 14, paddingInlineLG: 24,
      contentFontSize: 14, contentFontSizeSM: 13, contentFontSizeLG: 15,
      borderRadius: 9, borderRadiusSM: 8, borderRadiusLG: 10,
      primaryShadow: "none", defaultShadow: "0 1px 2px rgba(20, 20, 20, 0.05)", dangerShadow: "none",
      defaultBorderColor: "#dededa", defaultHoverBg: "#f4f4f2", defaultHoverBorderColor: "#c9c9c5", defaultHoverColor: INK, defaultActiveBg: MINT,
      fontWeight: 500,
    },
    // Text sits clear of the rounded ends: more room at the sides than a square field needs.
    Input: { activeShadow: "0 0 0 3px rgba(168, 214, 155, 0.45)", hoverBorderColor: "#6a6a6a", activeBorderColor: INK, paddingInline: 16, paddingInlineLG: 18, paddingInlineSM: 12, paddingBlock: 6 },
    InputNumber: { activeShadow: "0 0 0 3px rgba(168, 214, 155, 0.45)", hoverBorderColor: "#6a6a6a", activeBorderColor: INK },
    Select: { activeOutlineColor: "rgba(168, 214, 155, 0.45)", hoverBorderColor: "#6a6a6a", activeBorderColor: INK, optionSelectedBg: MINT, optionSelectedColor: INK, optionActiveBg: "#f4f4f2", optionSelectedFontWeight: 600,
      // The UI kit's menus: roomier rows, picked ones as mint chips in the field.
      optionHeight: 34, optionPadding: "6px 10px", multipleItemBg: MINT, multipleItemBorderColor: "#e3eedf" },
    DatePicker: { activeShadow: "0 0 0 3px rgba(168, 214, 155, 0.45)", hoverBorderColor: "#6a6a6a", activeBorderColor: INK, cellActiveWithRangeBg: MINT },
    // The selected filter is ink, as on the components page.
    Segmented: { itemSelectedBg: INK, itemSelectedColor: "#ffffff", trackBg: "#ffffff", trackPadding: 3, borderRadius: 999, borderRadiusSM: 999 },
    Tabs: { inkBarColor: INK, itemSelectedColor: INK, itemHoverColor: INK, itemActiveColor: INK },
    Table: { headerBg: "#fbfbfa", headerColor: "#6a6a6a", rowHoverBg: MINT, rowSelectedBg: MINT, rowSelectedHoverBg: "#e8f2e3", borderColor: "#ececea" },
    Card: { borderRadiusLG: 22 },
    // Dialogs: a large title, a round close button, room around the fields (the rest in app/globals.css).
    Modal: { borderRadiusLG: 28, titleFontSize: 22, titleLineHeight: 1.3, modalCloseBtnSize: 36 },
    Tag: { borderRadiusSM: 999, defaultBg: "#f0f0ee" },
    Menu: { itemSelectedBg: MINT, itemSelectedColor: INK, itemBorderRadius: 999 },
    Progress: { defaultColor: SAGE, remainingColor: "#e3eedf" },
    Switch: { colorPrimary: INK, colorPrimaryHover: "#2b2b2b" },
    Checkbox: { colorPrimary: INK, colorPrimaryHover: "#2b2b2b", borderRadiusSM: 6 },
    Radio: { colorPrimary: INK },
  },
};

// In place of Ant's grey "No data" box: a plain line in our words.
const PICKERS = new Set(["Select", "Cascader", "TreeSelect", "AutoComplete", "Transfer"]);

export function AntTheme({ children }: { children: ReactNode }) {
  return (
    <AntdRegistry>
      <ConfigProvider theme={ANT_THEME} renderEmpty={(component) => <p className="px-1 py-3 text-center text-meta text-ink-3">{PICKERS.has(component ?? "") ? "No options available." : "No data."}</p>}>
        {children}
      </ConfigProvider>
    </AntdRegistry>
  );
}
