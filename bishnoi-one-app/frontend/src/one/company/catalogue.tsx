"use client";

import { Switch } from "antd";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Sheet } from "@/src/platform/ui/sheet";
import { Tip } from "@/src/platform/ui/tip";
import { switchCatalogue } from "./actions";
import type { CatalogueEntry } from "./types";

// The app catalogue (feature plan step 6, decision 10, like Odoo's Apps and Zoho's): a company turns
// on only the apps it uses and, inside each, only the features it needs; what's off is hidden from
// menus, forms and reports in every app. Each switch sits on what it changes.

export function CatalogueBoard({ apps }: { apps: CatalogueEntry[] }) {
  const ready = apps.filter((a) => !a.later);
  const coming = apps.filter((a) => a.later);
  return (
    <div className="space-y-6">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {ready.map((a) => (
          <AppCard key={a.key} app={a} />
        ))}
      </div>
      {coming.length > 0 && (
        <section>
          <h2 className="mb-2 text-caps text-ink-3 uppercase">Coming</h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {coming.map((a) => (
              <AppCard key={a.key} app={a} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function AppCard({ app }: { app: CatalogueEntry }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [pending, setPending] = useState<string | null>(null);

  function flip(key: string, on: boolean, label: string) {
    setPending(key);
    start(async () => {
      const r = await switchCatalogue(key, on);
      setPending(null);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`${label} ${on ? "on" : "off"}`, { description: on ? undefined : "Hidden from menus, forms and reports for everyone." });
      router.refresh();
    });
  }

  const blocked = app.later || (!app.on && !app.available);
  return (
    <Sheet className={`flex flex-col px-5 py-4 ${app.on ? "" : "bg-bench/40"}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-base font-semibold text-ink">{app.name}</p>
          <p className="text-sm text-ink-3">{app.job}</p>
        </div>
        <Tip tip={app.later ? "On the plan, not ready yet" : blocked ? "Not available yet: ask Bishnoi One's operators" : app.on ? `Turn ${app.name} off` : `Turn ${app.name} on`}>
          <Switch aria-label={`${app.name} on or off`} checked={app.on} disabled={blocked || busy} loading={pending === app.key} onChange={(on) => flip(app.key, on, app.name)} />
        </Tip>
      </div>
      {app.switches.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-rule pt-3">
          {app.switches.map((s) => (
            <li key={s.key} className="flex items-center gap-3">
              <span className={`min-w-0 flex-1 text-sm ${app.on && !s.later ? "text-ink-2" : "text-ink-3"}`}>
                {s.label}
                {s.later && <span className="ml-2 text-meta">Coming</span>}
                {s.hint && !s.later && (
                  <Tip tip={s.hint}>
                    <span className="ml-1 cursor-help text-meta text-ink-3">ⓘ</span>
                  </Tip>
                )}
              </span>
              <Switch
                size="small"
                aria-label={`${s.label} on or off`}
                checked={s.on}
                disabled={!app.on || s.later || busy}
                loading={pending === s.key}
                onChange={(on) => flip(s.key, on, s.label)}
              />
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}
