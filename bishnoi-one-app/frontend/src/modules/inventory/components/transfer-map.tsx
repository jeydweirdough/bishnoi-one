"use client";

import "leaflet/dist/leaflet.css";
import { ChevronRight, Clock, MapPin, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/inventory/platform/ui/button";
import { Combobox } from "@/src/modules/inventory/platform/ui/pickers";
import { locateWarehouse } from "@/src/modules/inventory/actions/inventory";
import { TRANSFER_STATUSES } from "@/src/modules/inventory/lib/labels";
import type { MapWarehouse, TransferRoute } from "@/src/modules/inventory/lib/types";
import { TransferStamp } from "@/src/modules/inventory/components/stamps";

// Transfers as trips, the way a dispatcher reads them: the list on the left
// (status, from and to, how long it has been at its step), the map on the right
// with each warehouse pinned and each transfer drawn from one pin to the other.
// Picking a card brings its route forward and shows it beside the map. A
// warehouse with no pin is listed, and "Find on map" places it from its address.

/** since: how long at this step, short ("2 h 5 m"); sinceLong: in words ("2 h 5 m on the road"). */
export type Shown = TransferRoute & { since: string; sinceLong: string; late: boolean; when: string };

const INK = "#141414";
const SAGE = "#4f7f44";
const FADED = "#b9bdb5";

function dashFor(status: TransferRoute["status"]): string | undefined {
  // Not on the road yet: dashed. On the road: solid. Arrived: thin and grey.
  return status === "in_transit" || status === "received" ? undefined : "6 8";
}

export function TransferMap({ transfers, warehouses, mayLocate }: { transfers: Shown[]; warehouses: MapWarehouse[]; mayLocate: boolean }) {
  const router = useRouter();
  const [tab, setTab] = useState<"transfers" | "warehouses">("transfers");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [picked, setPicked] = useState<string | null>(transfers.find((t) => t.status === "in_transit")?.id ?? transfers[0]?.id ?? null);
  const [refreshing, startRefresh] = useTransition();
  const [locating, setLocating] = useState<string | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<import("leaflet").Map | null>(null);
  const layers = useRef<import("leaflet").LayerGroup | null>(null);
  const leaflet = useRef<typeof import("leaflet") | null>(null);
  const [ready, setReady] = useState(false);

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return transfers.filter(
      (t) =>
        (!status || t.status === status) &&
        (!needle || [t.number, t.from.name, t.to.name, t.from.code, t.to.code, t.firstItem ?? ""].some((s) => s.toLowerCase().includes(needle))),
    );
  }, [transfers, q, status]);
  const chosen = transfers.find((t) => t.id === picked) ?? null;
  const unpinned = warehouses.filter((w) => !w.pin);

  // The map, made once.
  useEffect(() => {
    let gone = false;
    import("leaflet").then((L) => {
      if (gone || !box.current || map.current) return;
      leaflet.current = L;
      map.current = L.map(box.current, { zoomControl: false, scrollWheelZoom: true }).setView([12.3, 122.6], 6); // the Philippines
      L.control.zoom({ position: "bottomright" }).addTo(map.current);
      // OpenStreetMap, as the CRM's routes use; greyed (below) so the routes stand out.
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map.current);
      layers.current = L.layerGroup().addTo(map.current);
      setReady(true);
    });
    return () => {
      gone = true;
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // The pins and routes, drawn again whenever the list or the pick changes.
  useEffect(() => {
    const L = leaflet.current;
    if (!ready || !L || !map.current || !layers.current) return;
    layers.current.clearLayers();
    const bounds: [number, number][] = [];
    for (const t of shown) {
      if (!t.fromPin || !t.toPin) continue;
      const on = t.id === picked;
      const line: [number, number][] = [
        [t.fromPin.latitude, t.fromPin.longitude],
        [t.toPin.latitude, t.toPin.longitude],
      ];
      L.polyline(line, {
        color: on ? SAGE : t.status === "received" ? FADED : INK,
        weight: on ? 5 : 3,
        opacity: on ? 1 : 0.55,
        dashArray: dashFor(t.status),
      })
        .on("click", () => setPicked(t.id))
        .bindTooltip(`${t.number} · ${TRANSFER_STATUSES[t.status]}`)
        .addTo(layers.current);
    }
    for (const w of warehouses) {
      if (!w.pin) continue;
      const at: [number, number] = [w.pin.latitude, w.pin.longitude];
      const end = chosen && (chosen.from.id === w.id || chosen.to.id === w.id);
      const color = chosen?.to.id === w.id ? SAGE : INK;
      L.marker(at, {
        icon: L.divIcon({
          className: "",
          html: `<span style="display:grid;place-items:center;width:${end ? 38 : 32}px;height:${end ? 38 : 32}px;border-radius:999px;background:${end ? color : "#fff"};color:${end ? "#fff" : INK};border:2px solid ${color};font:600 12px Poppins,sans-serif;box-shadow:0 4px 12px rgba(0,0,0,.18)">${w.code}</span>`,
          iconSize: [end ? 38 : 32, end ? 38 : 32],
          iconAnchor: [end ? 19 : 16, end ? 19 : 16],
        }),
      })
        .bindTooltip(`${w.name}${w.address ? ` · ${w.address}` : ""}`)
        .addTo(layers.current);
      bounds.push(at);
    }
    if (chosen?.fromPin && chosen.toPin) {
      map.current.fitBounds(
        [
          [chosen.fromPin.latitude, chosen.fromPin.longitude],
          [chosen.toPin.latitude, chosen.toPin.longitude],
        ],
        // Clear of the details panel at the top left.
        { paddingTopLeft: [340, 60], paddingBottomRight: [60, 60], maxZoom: 11 },
      );
    } else if (bounds.length) {
      map.current.fitBounds(bounds, { padding: [60, 60], maxZoom: 11 });
    }
  }, [ready, shown, warehouses, picked, chosen]);

  async function locate(w: MapWarehouse) {
    setLocating(w.id);
    const r = await locateWarehouse(w.id);
    setLocating(null);
    if (r.ok) toast.success(`${w.name} is on the map`);
    else toast.error(r.error);
  }

  return (
    <div className="grid h-[calc(100dvh-14rem)] min-h-[34rem] overflow-hidden rounded-xl border border-rule bg-sheet lg:grid-cols-[23rem_minmax(0,1fr)]">
      <aside className="flex min-h-0 flex-col border-b border-rule lg:border-r lg:border-b-0">
        <div className="px-5 pt-5">
          <h2 className="text-xl font-semibold text-ink">Map</h2>
          <div className="mt-3 flex gap-5 border-b border-rule" role="tablist">
            {(
              [
                ["transfers", "Transfers", transfers.length],
                ["warehouses", "Warehouses", warehouses.length],
              ] as const
            ).map(([key, label, n]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={tab === key}
                onClick={() => setTab(key)}
                className={`-mb-px border-b-2 pb-2 text-sm ${tab === key ? "border-ink font-semibold text-ink" : "border-transparent text-ink-3 hover:text-ink"}`}
              >
                {label} <span className="ml-1 text-meta text-ink-3">{n}</span>
              </button>
            ))}
          </div>
          {tab === "transfers" && (
            <div className="mt-3 flex gap-2">
              <label className="relative min-w-0 flex-1">
                <span className="sr-only">Search transfers</span>
                <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
                <input
                  type="search"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search transfers"
                  className="block h-9 w-full rounded-lg border border-control bg-sheet pr-3 pl-10 text-sm text-ink placeholder:text-ink-3/80 hover:border-ink-3 focus:border-ink focus:outline-none"
                />
              </label>
              <Combobox
                className="!w-32"
                value={status}
                onChange={(v) => setStatus(String(v ?? ""))}
                options={[{ value: "", label: "All" }, ...(["requested", "approved", "in_transit", "received", "draft"] as const).map((s) => ({ value: s, label: TRANSFER_STATUSES[s] }))]}
              />
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {tab === "transfers" &&
            (shown.length === 0 ? (
              <p className="py-6 text-center text-sm text-ink-3">No matching transfers.</p>
            ) : (
              shown.map((t) => {
                const on = t.id === picked;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setPicked(t.id)}
                    aria-pressed={on}
                    className={`block w-full rounded-lg border bg-sheet px-4 py-3 text-left transition-colors ${on ? "border-sage-deep shadow-[0_0_0_1px_var(--color-sage-deep)]" : "border-rule hover:border-rule-strong"}`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-2">
                        <span className="text-meta font-semibold whitespace-nowrap text-ink-2">{t.number}</span>
                        <TransferStamp status={t.status} />
                      </span>
                      <span className={`flex shrink-0 items-center gap-1 text-right text-meta whitespace-nowrap tabular-nums ${t.late ? "font-semibold text-danger" : "text-ink-3"}`}>
                        <Clock className="size-3.5" aria-hidden />
                        {t.since}
                      </span>
                    </span>
                    <span className="mt-2 flex items-baseline justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-ink">{t.firstItem ?? "No lines"}{t.lineCount > 1 ? ` and ${t.lineCount - 1} more` : ""}</span>
                      <span className="shrink-0 text-sm font-semibold text-ink tabular-nums">{t.units.toLocaleString()} units</span>
                    </span>
                    <span className="mt-2 grid grid-cols-[0.75rem_minmax(0,1fr)] gap-x-2 text-meta">
                      <span className="mt-1 size-2.5 rounded-full border-2 border-ink" aria-hidden />
                      <span className="truncate text-ink-2">
                        {t.from.name}
                        {t.fromAddress ? ` · ${t.fromAddress}` : ""}
                      </span>
                      <span className="ml-[0.28rem] h-3 border-l border-dashed border-rule-strong" aria-hidden />
                      <span />
                      <span className="mt-1 size-2.5 rounded-full bg-sage-deep" aria-hidden />
                      <span className="truncate text-ink-2">
                        {t.to.name}
                        {t.toAddress ? ` · ${t.toAddress}` : ""}
                      </span>
                    </span>
                    <span className="mt-3 flex items-center justify-between border-t border-rule pt-2 text-meta text-ink-3">
                      <span>{t.when}</span>
                      <ChevronRight className="size-4" aria-hidden />
                    </span>
                  </button>
                );
              })
            ))}

          {tab === "warehouses" &&
            warehouses.map((w) => (
              <div key={w.id} className="rounded-lg border border-rule px-4 py-3">
                <p className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">{w.name}</span>
                  <span className="text-meta font-semibold text-ink-3">{w.code}</span>
                </p>
                <p className="mt-0.5 text-meta text-ink-3">{w.address ?? "No address"}</p>
                <p className="mt-2 flex items-center justify-between gap-2 text-meta">
                  {w.pin ? (
                    <span className="flex items-center gap-1 text-sage-deep">
                      <MapPin className="size-3.5" aria-hidden />
                      Mapped
                    </span>
                  ) : (
                    <span className="text-ink-3">Not mapped</span>
                  )}
                  {!w.pin && mayLocate && (
                    <Button size="sm" disabled={!w.address || locating === w.id} onClick={() => locate(w)} title={w.address ? undefined : "Add an address first"}>
                      {locating === w.id ? "Locating…" : "Locate on map"}
                    </Button>
                  )}
                </p>
              </div>
            ))}
        </div>
      </aside>

      <div className="relative min-h-[28rem]">
        <div ref={box} className="absolute inset-0 bg-bench [&_.leaflet-tile-pane]:[filter:grayscale(1)_brightness(1.06)_contrast(0.92)]" role="img" aria-label="Transfers between warehouses on a map" />
        <div className="pointer-events-none absolute inset-x-4 top-4 z-[500] flex items-start justify-between gap-3">
          {chosen ? (
            <div className="pointer-events-auto w-72 rounded-lg border border-rule bg-sheet p-4 shadow-overlay">
              <p className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-ink">{chosen.number}</span>
                <TransferStamp status={chosen.status} />
              </p>
              <p className="mt-2 text-meta text-ink-2">
                {chosen.from.name} → {chosen.to.name}
              </p>
              <p className="mt-0.5 text-meta text-ink-3">
                {chosen.units.toLocaleString()} units · {chosen.lineCount} line{chosen.lineCount === 1 ? "" : "s"} · {chosen.sinceLong}
              </p>
              {(!chosen.fromPin || !chosen.toPin) && <p className="mt-2 text-meta text-danger">A warehouse on this transfer is not mapped, so the route cannot be shown.</p>}
              <Link href={`/inventory/transfers/${chosen.id}`} className="mt-3 flex h-9 items-center justify-center gap-1.5 rounded-lg border border-ink text-sm font-medium text-ink hover:bg-hema-tint">
                Open transfer
                <ChevronRight className="size-4" aria-hidden />
              </Link>
            </div>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={() => startRefresh(() => router.refresh())}
            className="pointer-events-auto inline-flex h-9 items-center gap-2 rounded-lg border border-rule bg-sheet px-4 text-sm text-ink shadow-overlay hover:bg-hema-tint"
          >
            <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden />
            Refresh
          </button>
        </div>
        {unpinned.length > 0 && (
          <div className="absolute bottom-4 left-4 z-[500] max-w-sm rounded-lg border border-rule bg-sheet px-4 py-2.5 text-meta text-ink-2 shadow-overlay">
            {unpinned.map((w) => w.name).join(", ")} {unpinned.length === 1 ? "is" : "are"} not mapped.{" "}
            <button type="button" onClick={() => setTab("warehouses")} className="font-semibold text-ink underline">
              Locate on map
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
