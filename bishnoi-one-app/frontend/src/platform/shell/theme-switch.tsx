"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/src/components/ui/button";

const CYCLE = ["light", "dark", "system"] as const;
const SAYS = { light: "Light", dark: "Dark", system: "As the computer is set" } as const;

/** Studio Admin's theme switch: light, dark, or as the computer is set, one click each, kept in this browser. */
export function ThemeSwitch() {
  const { theme = "light", setTheme } = useTheme();
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  // Until the page is in the browser the theme isn't known: light, as the server drew it.
  const now = ready && (CYCLE as readonly string[]).includes(theme) ? (theme as (typeof CYCLE)[number]) : "light";
  const next = CYCLE[(CYCLE.indexOf(now) + 1) % CYCLE.length];
  return (
    <Button size="icon" variant="ghost" onClick={() => setTheme(next)} aria-label={`Theme: ${SAYS[now]}. Change to ${SAYS[next]}`} title={`Theme: ${SAYS[now]}`}>
      {now === "system" ? <Monitor /> : now === "dark" ? <Moon /> : <Sun />}
    </Button>
  );
}
