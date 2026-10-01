"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { Pin, RoutePoint, Visit } from "./types";

type MapVisit = Visit & { clinic: Pin | null };

// The day on a map (OpenStreetMap, through Leaflet): the trail as a line, a
// dot where it started and one where it ended, each visit where it was logged
// (blue at the clinic, red elsewhere, grey where there's no pin to tell), and
// each clinic's pin as a small square.
const HEMA = "#2b2f6e";
const DANGER = "#b42318";
const GREY = "#8a8f98";

export function RouteMap({ points, visits }: { points: RoutePoint[]; visits: MapVisit[] }) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let map: import("leaflet").Map | null = null;
    let gone = false;
    import("leaflet").then((L) => {
      if (gone || !box.current) return;
      map = L.map(box.current, { scrollWheelZoom: false });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);

      const bounds: [number, number][] = [];
      if (points.length) {
        const line = points.map((p) => [p.latitude, p.longitude] as [number, number]);
        L.polyline(line, { color: HEMA, weight: 4, opacity: 0.75 }).addTo(map);
        L.circleMarker(line[0], { radius: 6, color: HEMA, fillColor: "#fff", fillOpacity: 1, weight: 3 }).bindTooltip("Started here").addTo(map);
        L.circleMarker(line.at(-1)!, { radius: 6, color: HEMA, fillColor: HEMA, fillOpacity: 1 }).bindTooltip("Last seen here").addTo(map);
        bounds.push(...line);
      }
      for (const v of visits) {
        if (v.clinic) {
          const at: [number, number] = [v.clinic.latitude, v.clinic.longitude];
          L.rectangle(
            [
              [at[0] - 0.00012, at[1] - 0.00012],
              [at[0] + 0.00012, at[1] + 0.00012],
            ],
            { color: HEMA, weight: 1, fillOpacity: 0.25 },
          )
            .bindTooltip(`${v.company.name}: clinic`)
            .addTo(map);
          bounds.push(at);
        }
        if (v.location) {
          const at: [number, number] = [v.location.latitude, v.location.longitude];
          const color = v.atClinic === true ? HEMA : v.atClinic === false ? DANGER : GREY;
          L.circleMarker(at, { radius: 9, color, fillColor: color, fillOpacity: 0.85, weight: 2 })
            .bindTooltip(`${v.company.name}${v.atClinic === false && v.distanceM !== null ? ` · logged ${v.distanceM} m from the clinic` : ""}`)
            .addTo(map);
          bounds.push(at);
        }
      }
      if (bounds.length) map.fitBounds(bounds, { padding: [32, 32], maxZoom: 17 });
      else map.setView([14.5995, 120.9842], 11); // Manila, when there's nothing to show
    });
    return () => {
      gone = true;
      map?.remove();
    };
  }, [points, visits]);

  return <div ref={box} role="img" aria-label="The day's route on a map" className="h-[28rem] w-full rounded-[3px] bg-bench" />;
}
