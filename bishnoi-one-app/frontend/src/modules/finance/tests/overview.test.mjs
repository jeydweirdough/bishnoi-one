// The Overview's plain rules (src/modules/finance/overview/lib.ts): its wording, where each card
// goes, and that a saved choice can only ever show what the person may still see.

import assert from "node:assert/strict";
import test from "node:test";

const { LAYOUT, MAX_CARDS, agoText, cleanPicks, pl, place, readPicks, short, writePicks } = await import("../overview/lib.ts");

test("counts read as people say them", () => {
  assert.equal(pl(1, "bill"), "1 bill");
  assert.equal(pl(3, "entry"), "3 entries");
  assert.equal(pl(0, "invoice"), "0 invoices");
});

test("chart labels shorten pesos, from centavos", () => {
  assert.equal(short(0), "₱0");
  assert.equal(short(9_500), "₱95");
  assert.equal(short(34_000_000), "₱340K");
  assert.equal(short(120_000_000), "₱1.2M");
  assert.equal(short(-34_000_000), "-₱340K");
});

test("a lead and up to five cards leave no hole in the four columns", () => {
  const widths = { c1: 1, c2: 2, c4: 4 };
  for (let n = 0; n <= MAX_CARDS; n++) {
    assert.equal(LAYOUT[n].length, n + 1);
    assert.equal(LAYOUT[n].reduce((sum, s) => sum + widths[s], 0) % 4, 0);
  }
});

test("a wide card takes a wide slot when there is one", () => {
  const cards = [{ key: "a", wide: false }, { key: "b", wide: false }, { key: "c", wide: true }, { key: "d", wide: false }];
  const { spans, cards: placed } = place(cards);
  assert.equal(spans[placed.findIndex((c) => c.key === "c")], "c2");
  assert.equal(new Set(placed.map((c) => c.key)).size, 4);
});

test("a saved choice keeps only what's still allowed, and at most five", () => {
  assert.deepEqual(cleanPicks(["ar", "cash", "gone"], ["ar", "ap"]), ["ar"]);
  assert.deepEqual(cleanPicks(["a", "b", "c", "d", "e", "f"], ["a", "b", "c", "d", "e", "f"]).length, 5);
  assert.equal(cleanPicks("nonsense", ["ar"]), null);
});

test("the page works without browser storage", () => {
  globalThis.window = { localStorage: { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } } };
  assert.equal(readPicks("u1", ["ar"]), null);
  assert.doesNotThrow(() => writePicks("u1", ["ar"]));
  assert.doesNotThrow(() => writePicks("u1", null));
  delete globalThis.window;
});

test("each person's choice is saved under their own id", () => {
  const saved = new Map();
  globalThis.window = { localStorage: { getItem: (k) => saved.get(k) ?? null, setItem: (k, v) => saved.set(k, v), removeItem: (k) => saved.delete(k) } };
  writePicks("u1", ["ar"]);
  assert.deepEqual(readPicks("u1", ["ar"]), ["ar"]);
  assert.equal(readPicks("u2", ["ar"]), null);
  writePicks("u1", null);
  assert.equal(readPicks("u1", ["ar"]), null);
  delete globalThis.window;
});

test("the time since the figures were read", () => {
  assert.equal(agoText(3), "updated just now");
  assert.equal(agoText(40), "updated 40 seconds ago");
  assert.equal(agoText(130), "updated 2 minutes ago");
});
