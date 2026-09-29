// Builds the screens of each app in Nabhi.exe as a small standalone server
// (Next.js "standalone" output), into nabhi-desktop/dist/web/<app>/.
//
//   node scripts/build-web.mjs            all apps
//   node scripts/build-web.mjs crm        one
//
// Each is built with the other apps' addresses on this PC (lib/apps.mjs), so
// the sidebar's links between apps work inside Nabhi.exe.

import { spawnSync } from "node:child_process";
import { cpSync, existsSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { APPS, publicUrls } from "../lib/apps.mjs";

const desktop = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(desktop, "..");
const wanted = process.argv.slice(2);
const apps = wanted.length ? wanted : Object.keys(APPS);

for (const app of apps) {
  if (!APPS[app]) throw new Error(`Unknown app ${app}; use ${Object.keys(APPS).join(", ")}`);
  const frontend = join(repo, APPS[app].folder, "frontend");
  console.log(`\n== Building ${APPS[app].name} screens`);
  const built = spawnSync("npx next build", {
    cwd: frontend,
    stdio: "inherit",
    shell: true,
    env: { ...process.env, NABHI_DESKTOP: "1", NEXT_TELEMETRY_DISABLED: "1", NODE_OPTIONS: "--max-old-space-size=4096", ...publicUrls() },
  });
  if (built.status !== 0) process.exit(built.status ?? 1);
  const standalone = join(frontend, ".next", "standalone");
  // server.js sits at the top, or under frontend/ when Next traced from the repo's root
  const inner = ["", "frontend"].find((dir) => existsSync(join(standalone, dir, "server.js")));
  if (inner === undefined) throw new Error(`${app}: no standalone server was made (is output: "standalone" set for NABHI_DESKTOP?)`);
  const out = join(desktop, "dist", "web", app);
  rmSync(out, { recursive: true, force: true });
  cpSync(standalone, out, { recursive: true });
  cpSync(join(frontend, ".next", "static"), join(out, inner, ".next", "static"), { recursive: true });
  if (existsSync(join(frontend, "public"))) cpSync(join(frontend, "public"), join(out, inner, "public"), { recursive: true });
  // where Nabhi.exe finds the server
  writeFileSync(join(out, "nabhi-web.json"), JSON.stringify({ app, server: inner ? `${inner}/server.js` : "server.js" }, null, 2));
  console.log(`   -> ${out}`);
}
