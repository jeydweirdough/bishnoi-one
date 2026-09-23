import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  
  turbopack: {
    // core is a sibling folder, and Turbopack resolves nothing outside its root.
    root: path.resolve(import.meta.dirname, ".."),
  },
  poweredByHeader: false,
};

export default nextConfig;
