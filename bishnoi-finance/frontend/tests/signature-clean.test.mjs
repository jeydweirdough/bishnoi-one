// The signature clean-up (src/signature/clean.ts), on made-up pictures: ink kept and
// made black, paper made transparent even where a shadow falls on it, an already
// transparent picture recognised, and the ink's box found.
// Run: node --import ./tests/support/register.mjs --test "tests/*.test.mjs"

import assert from "node:assert/strict";
import test from "node:test";
import { inkBox, inkFromPaper, isTransparent } from "../src/signature/clean.ts";

const W = 200;
const H = 60;

/** White paper darkening to grey on the right (a shadow), with a dark stroke across the middle. */
function photo() {
  const d = new Uint8ClampedArray(W * H * 4);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const paper = 245 - Math.round((x / W) * 85); // 245 on the left, 160 on the right
      const ink = y >= 28 && y <= 32 && x >= 20 && x <= 180;
      const v = ink ? Math.round(paper * 0.25) : paper;
      const i = (y * W + x) * 4;
      d[i] = d[i + 1] = d[i + 2] = v;
      d[i + 3] = 255;
    }
  return d;
}

const alphaAt = (d, x, y) => d[(y * W + x) * 4 + 3];

test("paper becomes transparent, even in the shadow; ink stays, black", () => {
  const out = inkFromPaper(photo(), W, H, 0.5);
  assert.equal(alphaAt(out, 10, 5), 0); // bright paper
  assert.equal(alphaAt(out, 190, 5), 0); // shadowed paper (160) is still paper
  assert.ok(alphaAt(out, 30, 30) > 200 && alphaAt(out, 170, 30) > 200); // ink, bright side and shadow side
  const i = (30 * W + 30) * 4;
  assert.deepEqual([out[i], out[i + 1], out[i + 2]], [0, 0, 0]); // black
});

test("the ink's box is found, with a margin", () => {
  const box = inkBox(inkFromPaper(photo(), W, H, 0.5), W, H);
  assert.ok(box && box.x <= 20 && box.x >= 10 && box.y <= 28 && box.y + box.h >= 33 && box.x + box.w >= 181);
});

test("a picture that's already transparent is recognised", () => {
  const d = new Uint8ClampedArray(W * H * 4); // all transparent
  for (let x = 20; x < 180; x++) d[(30 * W + x) * 4 + 3] = 255; // one opaque stroke
  assert.equal(isTransparent(d), true);
  assert.equal(isTransparent(photo()), false);
});

test("a blank page has no signature", () => {
  const d = new Uint8ClampedArray(W * H * 4).fill(240);
  assert.equal(inkBox(inkFromPaper(d, W, H, 0.5), W, H), null);
});
