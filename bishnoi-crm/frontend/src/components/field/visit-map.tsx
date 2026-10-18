"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { Pin, Zone } from "./types";
import type { Where } from "./where";

// The visit form's map (OpenStreetMap, through Leaflet): where you are, and
// your doctors' clinics around you as dots in their zone's colour. Tapping a
// clinic picks that doctor. The one picked is ringed.

export type MapDoctor = { id: string; name: string; pin?: Pin | null; zone?: Zone | null };

const ZONE_COLOR: Record<Zone, string> = { red: "#e34948", yellow: "#eda100", green: "#1a8a52" };
const NO_ZONE = "#8a8f98";
const YOU = "#2a78d6";
// How far around you the map opens on: the nearest clinics, not the whole list.
const NEAR_M = 3000;

export function VisitMap({ doctors, here, picked, onPick, className = "h-56 sm:h-64" }: { doctors: MapDoctor[]; here: Where | null; picked: string; onPick: (id: string) => void; className?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<import("leaflet").Map | null>(null);
  const layer = useRef<import("leaflet").LayerGroup | null>(null);
  const leaflet = useRef<typeof import("leaflet") | null>(null);
  // How the map was last opened: not yet, on the clinics, or on you (the one that sticks).
  const fitted = useRef<"no" | "pins" | "here">("no");
  const pick = useRef(onPick);
  pick.current = onPick;

  // The map once; what's on it whenever the doctors, where you are, or the pick change.
  useEffect(() => {
    let gone = false;
    import("leaflet").then((L) => {
      if (gone || !box.current || map.current) return;
      leaflet.current = L;
      map.current = L.map(box.current, { zoomControl: true, attributionControl: true }).setView([14.5995, 120.9842], 11);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map.current);
      layer.current = L.layerGroup().addTo(map.current);
      draw();
      // Drawn inside a dialog that's still opening: measured again once it has.
      setTimeout(() => map.current?.invalidateSize(), 300);
    });
    return () => {
      gone = true;
      map.current?.remove();
      map.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => draw()); // eslint-disable-line react-hooks/exhaustive-deps

  function draw() {
    const L = leaflet.current;
    const m = map.current;
    const g = layer.current;
    if (!L || !m || !g) return;
    g.clearLayers();
    const pinned = doctors.filter((d) => d.pin);
    for (const d of pinned) {
      const at: [number, number] = [d.pin!.latitude, d.pin!.longitude];
      const color = d.zone ? ZONE_COLOR[d.zone] : NO_ZONE;
      const chosen = d.id === picked;
      L.circleMarker(at, { radius: chosen ? 11 : 8, color: chosen ? "#141414" : "#fff", weight: chosen ? 3 : 2, fillColor: color, fillOpacity: 0.95 })
        .bindTooltip(d.name, { direction: "top", offset: [0, -6] })
        .on("click", () => pick.current(d.id))
        .addTo(g);
    }
    if (here) {
      const at: [number, number] = [here.latitude, here.longitude];
      if (here.accuracyM) L.circle(at, { radius: here.accuracyM, color: YOU, weight: 1, fillColor: YOU, fillOpacity: 0.1 }).addTo(g);
      L.circleMarker(at, { radius: 7, color: "#fff", weight: 2, fillColor: YOU, fillOpacity: 1 }).bindTooltip("You are here").addTo(g);
    }
    // Opens once: on you and the clinics near you (or every clinic, when none is near).
    if (fitted.current === "here" || (fitted.current === "pins" && !here)) {
      const chosen = pinned.find((d) => d.id === picked);
      if (chosen) m.panTo([chosen.pin!.latitude, chosen.pin!.longitude]);
      return;
    }
    if (!here && !pinned.length) return;
    const near = here ? pinned.filter((d) => m.distance([here.latitude, here.longitude], [d.pin!.latitude, d.pin!.longitude]) <= NEAR_M) : pinned;
    const points: [number, number][] = [...(here ? [[here.latitude, here.longitude] as [number, number]] : []), ...(near.length ? near : pinned).map((d) => [d.pin!.latitude, d.pin!.longitude] as [number, number])];
    if (points.length === 1) m.setView(points[0], 16);
    else m.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: 17 });
    fitted.current = here ? "here" : "pins";
  }

  return <div ref={box} className={`w-full overflow-hidden rounded-xl border border-rule ${className}`} role="application" aria-label="Map of your doctors' clinics: tap one to pick it" />;
}
