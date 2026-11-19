import type { MetadataRoute } from "next";

// Bishnoi One as an app on the phone's home screen (Step 4H, 2026-11-18): field
// agents open it like any app, and public/sw.js lets it open without a signal.
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Bishnoi One",
    short_name: "Bishnoi One",
    description: "Customers, visits, stock and books for every team.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#f5f5f5",
    theme_color: "#f5f5f5",
    icons: [
      { src: "/brand/app-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/brand/app-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/brand/app-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [{ name: "Field", short_name: "Field", url: "/crm/field", icons: [{ src: "/brand/app-192.png", sizes: "192x192" }] }],
  };
}
