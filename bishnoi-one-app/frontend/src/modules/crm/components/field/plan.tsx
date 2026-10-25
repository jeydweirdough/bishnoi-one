"use client";

import { Dropdown } from "antd";
import { ChevronDown } from "lucide-react";
import { useOptimistic, useTransition } from "react";
import { toast } from "sonner";
import { setPlan } from "@/src/modules/crm/actions/field";
import type { DoctorPlan, Zone } from "@/src/modules/crm/components/field/types";
import { TIER_VISITS, ZONES } from "@/src/modules/crm/components/field/words";

// A doctor's tier and zone, set where the doctor is listed: two small pickers
// on the row. The change shows at once, and goes back if it can't be saved.

type Plan = Pick<DoctorPlan, "tier" | "zone">;

export function PlanPicker({ id, name, plan, editable }: { id: string; name: string; plan: Plan; editable: boolean }) {
  const [shown, show] = useOptimistic(plan, (now: Plan, change: Partial<Plan>) => ({ ...now, ...change }));
  const [, start] = useTransition();
  const save = (change: Partial<Plan>) =>
    start(async () => {
      show(change);
      const r = await setPlan(id, change);
      if (!r.ok) toast.error(r.error);
    });
  const zone = ZONES.find((z) => z.value === shown.zone);
  const tierLabel = shown.tier ? `Tier ${shown.tier}` : "No tier";
  if (!editable) {
    return (
      <span className="flex flex-wrap items-center gap-1.5">
        <TierTag tier={shown.tier} />
        <ZoneTag zone={shown.zone} />
      </span>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Dropdown
        trigger={["click"]}
        menu={{
          selectedKeys: [String(shown.tier ?? "")],
          items: [
            ...([1, 2, 3] as const).map((t) => ({ key: String(t), label: `Tier ${t} · ${TIER_VISITS[t]} ${TIER_VISITS[t] === 1 ? "visit" : "visits"} a month` })),
            { type: "divider" as const },
            { key: "", label: "No tier" },
          ],
          onClick: ({ key }) => save({ tier: key ? (Number(key) as 1 | 2 | 3) : null }),
        }}
      >
        <button suppressHydrationWarning type="button" aria-label={`${name}: ${tierLabel}. Change the tier`} className={`${PILL} ${shown.tier ? "bg-ink/8 text-ink" : "border border-dashed border-rule-strong text-ink-3"}`}>
          {shown.tier ? `T${shown.tier}` : "Tier"}
          <ChevronDown className="size-3" aria-hidden />
        </button>
      </Dropdown>
      <Dropdown
        trigger={["click"]}
        menu={{
          selectedKeys: [shown.zone ?? ""],
          items: [
            ...ZONES.map((z) => ({
              key: z.value,
              label: (
                <span className="flex items-start gap-2">
                  <span className={`mt-1.5 size-2 shrink-0 rounded-full ${z.dot}`} aria-hidden />
                  <span>
                    <span className="block font-medium">{z.label}</span>
                    <span className="block text-meta text-ink-3">{z.when}</span>
                  </span>
                </span>
              ),
            })),
            { type: "divider" as const },
            { key: "", label: "No zone" },
          ],
          onClick: ({ key }) => save({ zone: (key || null) as Zone | null }),
        }}
      >
        <button suppressHydrationWarning
          type="button"
          aria-label={`${name}: ${zone ? `${zone.label} zone` : "no zone"}. Change the zone`}
          className={`${PILL} ${zone ? zone.pill : "border border-dashed border-rule-strong text-ink-3"}`}
        >
          {zone && <span className={`size-1.5 rounded-full ${zone.dot}`} aria-hidden />}
          {zone ? zone.label : "Zone"}
          <ChevronDown className="size-3" aria-hidden />
        </button>
      </Dropdown>
    </span>
  );
}

const PILL = "inline-flex h-6 items-center gap-1 rounded-full px-2 text-meta font-semibold transition-colors hover:brightness-95";

export function TierTag({ tier }: { tier: number | null }) {
  if (!tier) return <span className="text-meta text-ink-3">No tier</span>;
  return <span className={`${PILL} bg-ink/8 text-ink`}>T{tier}</span>;
}

export function ZoneTag({ zone }: { zone: Zone | null }) {
  const z = ZONES.find((x) => x.value === zone);
  if (!z) return <span className="text-meta text-ink-3">No zone</span>;
  return (
    <span className={`${PILL} ${z.pill}`}>
      <span className={`size-1.5 rounded-full ${z.dot}`} aria-hidden />
      {z.label}
    </span>
  );
}
