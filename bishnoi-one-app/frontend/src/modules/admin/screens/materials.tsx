"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Material } from "@/src/modules/admin/actions/materials";
import { MaterialForm } from "@/src/modules/admin/components/materials/material-form";
import { NeededCell, waitingWords } from "@/src/modules/admin/components/materials/urgency";
import { MATERIAL_STATUS, REVIEW } from "@/src/modules/admin/components/materials/words";
import { CellView } from "@/src/modules/admin/screens/operations";
import { RecordTable } from "@/src/modules/admin/components/record-table";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";

type Data = { items: Material[]; kinds: string[]; linked: { pharmacy: boolean; crm: boolean } };

// What needs doing now comes first; then each stage.
const NOW: Record<string, { label: string; matches: (m: Material) => boolean }> = {
  late: { label: "Late", matches: (m) => m.urgency.tier === "overdue" },
  soon: { label: "Needed within 15 days", matches: (m) => m.urgency.tier === "urgent" },
  waiting: { label: "Waiting 3+ days", matches: (m) => (m.urgency.waiting?.days ?? 0) >= 3 },
  low: { label: "Low stock", matches: (m) => m.urgency.lowStock },
};
const FILTER: Record<string, string> = {
  ...Object.fromEntries(Object.entries(NOW).map(([k, v]) => [k, v.label])),
  ...Object.fromEntries(Object.entries(MATERIAL_STATUS).map(([k, v]) => [k, v.text])),
};

/** The figures that say what needs doing now, each only when there's something. */
function ActNow({ items }: { items: Material[] }) {
  const counts = Object.entries(NOW)
    .map(([key, v]) => ({ key, label: v.label, n: items.filter(v.matches).length }))
    .filter((c) => c.n > 0);
  if (counts.length === 0) return null;
  return (
    <div role="status" className="mb-4 flex flex-wrap items-center gap-2 rounded-[18px] bg-[#fbf0d9] px-4 py-3 text-[#8a5a00]">
      <span className="mr-1 text-sm font-semibold">Needs action now</span>
      {counts.map((c) => (
        <span key={c.key} className={`inline-flex h-[26px] items-center rounded-full px-3 text-[12.5px] font-medium ${c.key === "late" ? "bg-danger-tint text-danger" : "bg-sheet text-ink"}`}>
          {c.label} · {c.n}
        </span>
      ))}
      <span className="text-[12.5px]">Pick one under Show to see them.</span>
    </div>
  );
}

/**
 * Promotional materials, from design to giving them out: each one's stage, its
 * design's review, and what's in stock. A name opens the material.
 */
export function MaterialsScreen({ data, canCreate }: { data: Data; canCreate: boolean }) {
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const missing = [!data.linked.pharmacy && "Pharmacy (design reviews)", !data.linked.crm && "the CRM (distribution approvals)"].filter(Boolean);

  return (
    <>
      <PageHeader
        title="Promotional materials"
        actions={
          canCreate && (
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus className="size-4" aria-hidden />
              New material
            </Button>
          )
        }
      >
        Designed by marketing, approved by the pharmacist, produced by the executive office, and given out with the manager&apos;s approval.
      </PageHeader>

      {missing.length > 0 && (
        <p role="note" className="mb-4 rounded-[14px] bg-[#fbf0d9] px-4 py-2.5 text-meta text-[#8a5a00]">
          Admin is not connected to {missing.join(" or ")} yet, so that step can&apos;t be sent. Please contact your system administrator.
        </p>
      )}

      <ActNow items={data.items} />

      <RecordTable
        rows={data.items}
        searchLabel={`Search ${data.items.length} materials`}
        search={(m) => [m.title, m.kind, m.product, m.no].filter(Boolean).join(" ")}
        filter={{ label: "Show", options: FILTER, matches: (m, key) => (NOW[key] ? NOW[key].matches(m) : m.status === key) }}
        rowTone={(m) => (m.urgency.tier === "overdue" ? "bad" : null)}
        emptyIcon="approvals"
        empty={{ title: "No promotional materials yet", body: canCreate ? "Add the first material, then upload its design." : "They appear here once marketing adds them." }}
        columns={[
          {
            key: "title",
            label: "Material",
            render: (m) => <CellView cell={{ type: "who", name: m.title, sub: [m.kind, m.product].filter(Boolean).join(" · ") }} href={`/admin/materials/${m.id}`} />,
          },
          {
            key: "status",
            label: "Status",
            render: (m) => (
              <span className="block">
                <CellView cell={{ type: "tag", ...MATERIAL_STATUS[m.status], dot: true }} />
                {waitingWords(m.urgency) && <span className="mt-1 block text-[12.5px] font-medium text-[#8a5a00]">{waitingWords(m.urgency)}</span>}
              </span>
            ),
          },
          { key: "needed", label: "Needed by", render: (m) => <NeededCell material={m} /> },
          {
            key: "design",
            label: "Design",
            kind: "hide-sm",
            render: (m) => <CellView cell={{ type: "text", text: m.version ? `Version ${m.version}` : null, sub: m.review ? REVIEW[m.review].text : undefined }} />,
          },
          {
            key: "stock",
            label: "In stock",
            kind: "num",
            render: (m) => (
              <span className="block text-right">
                <span className="font-medium text-ink">{m.stock.toLocaleString()}</span>
                {m.reserved > 0 && <span className="block text-[12.5px] text-ink-3">{m.available.toLocaleString()} free</span>}
              </span>
            ),
          },
        ]}
      />

      {adding && <MaterialForm kinds={data.kinds} item={null} onClose={() => setAdding(false)} onSaved={(page) => router.push(`/admin/materials/${page.material.id}`)} />}
    </>
  );
}
