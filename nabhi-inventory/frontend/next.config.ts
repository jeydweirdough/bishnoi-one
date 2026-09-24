import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // core ships raw TypeScript, so Next compiles it with this app.
  
  turbopack: {
    // core is a sibling folder, and Turbopack resolves nothing outside
    // its root, so the root is the folder holding both.
    root: path.resolve(import.meta.dirname, ".."),
  },
  poweredByHeader: false,
};

export default nextConfig;
