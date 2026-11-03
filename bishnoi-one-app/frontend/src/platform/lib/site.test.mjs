import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";

const code = ts.transpileModule(readFileSync(new URL("./site.ts", import.meta.url), "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText;
const { isSameOriginRequest } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const request = (headers, url = "http://localhost:4301/api/assistant/chat") => ({ headers: new Headers(headers), url });

test("assistant origin checks use the public site behind a proxy and fail closed", () => {
  const previous = process.env.ONE_APP_URL;
  try {
    delete process.env.ONE_APP_URL;
    const proxy = {
      origin: "https://one.bishnoi.ai",
      "sec-fetch-site": "same-origin",
      "x-forwarded-host": "one.bishnoi.ai",
      "x-forwarded-proto": "https",
    };
    assert.equal(isSameOriginRequest(request(proxy)), true);
    assert.equal(isSameOriginRequest(request({ ...proxy, "x-forwarded-proto": "http", "cf-visitor": '{"scheme":"https"}' })), true);
    assert.equal(isSameOriginRequest(request({ ...proxy, origin: "https://evil.example" })), false);
    assert.equal(isSameOriginRequest(request({ ...proxy, origin: "https://other.bishnoi.ai", "sec-fetch-site": "same-site" })), false);
    assert.equal(isSameOriginRequest(request({ ...proxy, origin: "https://one.bishnoi.ai:8443" })), false);
    assert.equal(isSameOriginRequest(request({ ...proxy, "sec-fetch-site": "cross-site" })), false);
    assert.equal(isSameOriginRequest(request({ ...proxy, origin: "null" })), false);
    assert.equal(isSameOriginRequest(request({ host: "one.bishnoi.ai" })), false);
    assert.equal(isSameOriginRequest(request({ origin: "http://localhost:4301" })), true);

    process.env.ONE_APP_URL = "https://one.bishnoi.ai/";
    assert.equal(isSameOriginRequest(request({ origin: "https://one.bishnoi.ai", host: "localhost:4301" })), true);
    // Configured origin cannot be overridden by a caller's forwarded headers.
    assert.equal(isSameOriginRequest(request({ ...proxy, origin: "https://evil.example", "x-forwarded-host": "evil.example" })), false);
    process.env.ONE_APP_URL = "invalid";
    assert.equal(isSameOriginRequest(request(proxy)), false);
  } finally {
    if (previous === undefined) delete process.env.ONE_APP_URL;
    else process.env.ONE_APP_URL = previous;
  }
});
