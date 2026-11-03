import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";

const code = ts.transpileModule(readFileSync(new URL("./stream.ts", import.meta.url), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const { readAssistantStream } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
function stream(text, step = 1) {
  const encoded = new TextEncoder().encode(text);
  return new ReadableStream({ start(controller) { for (let n = 0; n < encoded.length; n += step) controller.enqueue(encoded.slice(n, n + step)); controller.close(); } });
}
const frame = value => `data: ${JSON.stringify(value)}\n\n`;
test("handles split UTF-8, frames and verified source metadata", async () => {
  const got = [];
  await readAssistantStream(stream(frame({ type: "sources", items: [{ label: "Finance" }], dateRange: { from: "2026-10-01", to: "2026-10-31" } }) + frame({ type: "text", text: "Jos\u00e9: PHP 1,000.00" }) + frame({ type: "done" })), event => got.push(event));
  assert.deepEqual(got.map(event => event.type), ["sources", "text", "done"]);
  assert.equal(got[0].dateRange.to, "2026-10-31");
});
test("refuses silently truncated and unknown-event streams", async () => {
  await assert.rejects(readAssistantStream(stream(frame({ type: "text", text: "Partial" })), () => {}), /complete/);
  await assert.rejects(readAssistantStream(stream(frame({ type: "sql" })), () => {}), /Unsupported/);
});
test("handles streamed error without pretending an answer completed", async () => {
  const got = [];
  await readAssistantStream(stream(frame({ type: "error", message: "No access" }), 4), event => got.push(event));
  assert.equal(got.length, 1);
  assert.equal(got[0].type, "error");
});
