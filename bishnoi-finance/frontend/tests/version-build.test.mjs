// The sidebar's "different builds" warning (src/version/build.ts): only when the
// screens and the API are both deployed (Vercel) builds from different commits. On a
// developer's computer they often differ with nothing wrong (fixed 2026-10-22).

import assert from "node:assert/strict";
import test from "node:test";

process.env.NEXT_PUBLIC_FINANCE_BUILD = "abc1234";
process.env.NEXT_PUBLIC_FINANCE_BUILD_SOURCE = "vercel";
const { buildsDiffer } = await import("../src/version/build.ts");

test("two deployed builds from different commits: warn", () => {
  assert.equal(buildsDiffer("def5678", "vercel"), true);
});

test("the same commit, or one built with uncommitted changes: no warning", () => {
  assert.equal(buildsDiffer("abc1234", "vercel"), false);
  assert.equal(buildsDiffer("abc1234-dirty", "vercel"), false);
});

test("an API on a developer's computer: no warning, whatever its commit", () => {
  assert.equal(buildsDiffer("def5678", "local"), false);
  assert.equal(buildsDiffer("def5678", undefined), false);
});
