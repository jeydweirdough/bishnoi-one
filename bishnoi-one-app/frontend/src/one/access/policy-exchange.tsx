"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Textarea } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { applyPolicyPreview, downloadPolicyVersion, exportAccessPolicy, generatePolicyPrompt, refreshPolicyHistory, validatePolicyResponse } from "./policy-actions";
import type { PolicyContext, PolicyPreview, PolicyVersion } from "./policy-types";

function download(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const area = "w-full rounded-lg border border-rule bg-white p-3 text-sm";
export function PolicyExchange({ context, initialHistory }: { context: PolicyContext; initialHistory: PolicyVersion[] }) {
  const router = useRouter();
  const [requirements, setRequirements] = useState("");
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [validation, setValidation] = useState<PolicyPreview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState("");
  const [history, setHistory] = useState(initialHistory);
  const [pending, start] = useTransition();
  const clear = () => { setValidation(null); setConfirmed(false); setError(""); setApplied(""); };

  function generate() {
    clear();
    start(async () => {
      const result = await generatePolicyPrompt(requirements);
      if (!result.ok) { setError(result.error); return; }
      setPrompt(result.data.prompt);
      // Generation includes a server round trip; some browsers require a new user
      // gesture for clipboard access. Keep a separate Copy button and visible text.
      try { await navigator.clipboard.writeText(result.data.prompt); toast.success("Prompt generated and copied"); }
      catch { toast.success("Prompt generated. Use Copy prompt or select the text below."); }
    });
  }
  function validate() {
    clear();
    start(async () => {
      const result = await validatePolicyResponse(response);
      if (!result.ok) { setError(result.error); return; }
      setValidation(result.data);
    });
  }
  function apply() {
    if (!confirmed || !validation?.valid || !validation.id) return;
    const id = validation.id;
    start(async () => {
      setError("");
      const result = await applyPolicyPreview(id, confirmed);
      if (!result.ok) { setError(result.error); setConfirmed(false); setValidation(null); return; }
      setApplied(`Applied ${result.data.roles} role policies. Version ${result.data.id}.`);
      setValidation(null); setConfirmed(false);
      toast.success("Access policy applied");
      const versions = await refreshPolicyHistory();
      if (versions.ok) setHistory(versions.data);
      router.refresh();
    });
  }
  const preview = validation?.preview;
  return <div className="space-y-5">
    <Sheet className="space-y-3 px-5 py-4">
      <h2 className="text-heading">1. Access requirements</h2>
      <p className="text-sm text-ink-3">Describe exactly which roles, records, actions, approval authority and limits you need. No AI service is connected. You choose where to paste the generated prompt; it includes your requirements and this company&apos;s current role policies and supported catalog.</p>
      <Field label="Access requirements">{field => <Textarea {...field} rows={6} maxLength={16000} value={requirements} disabled={pending} onChange={e => { setRequirements(e.target.value); setPrompt(""); clear(); }} placeholder="Describe the roles and their intended access, which existing access to keep or revoke, record scopes and any approval rules." />}</Field>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={pending || requirements.trim().length < 10} onClick={generate}>Generate &amp; copy AI prompt</Button>
        <Button disabled={pending} onClick={() => start(async () => { const r = await exportAccessPolicy(); if (r.ok) download("bishnoi-access-policy.json", r.data); else setError(r.error); })}>Export current policies</Button>
        <Button disabled={pending} onClick={() => download("bishnoi-access-policy.schema.json", context.schema)}>Download JSON schema</Button>
      </div>
      {prompt && <div className="space-y-2">
        <label className="block text-sm font-medium" htmlFor="access-ai-prompt">Generated prompt</label>
        <textarea id="access-ai-prompt" readOnly value={prompt} rows={8} className={`${area} font-mono text-xs`} onFocus={e => e.currentTarget.select()} />
        <Button onClick={async () => { try { await navigator.clipboard.writeText(prompt); toast.success("Prompt copied"); } catch { setError("Clipboard unavailable. Select and copy the prompt above."); } }}>Copy prompt</Button>
        <p className="text-sm text-ink-3">Paste into ChatGPT, Claude or another AI. Answer its necessary clarification questions in the same conversation. Do not request a final policy until critical ambiguities and unsupported requirements are resolved.</p>
      </div>}
    </Sheet>
    <Sheet className="space-y-3 px-5 py-4">
      <h2 className="text-heading">2. Paste AI response and validate</h2>
      <p className="text-sm text-ink-3">Paste one JSON object. Clarification responses display questions; they cannot be applied. Unsupported permissions, arbitrary conditions, administrator elevation and employee assignments are rejected.</p>
      <Field label="AI response JSON">{field => <Textarea {...field} rows={10} value={response} maxLength={200000} disabled={pending} onChange={e => { setResponse(e.target.value); clear(); }} className="font-mono text-xs" />}</Field>
      <Button variant="primary" disabled={pending || !response.trim()} onClick={validate}>{pending ? "Working..." : "Validate JSON & preview"}</Button>
      {validation && !validation.valid && <div role="status" className="space-y-2">
        {!!validation.errors?.length && <><p className="font-medium text-danger">JSON validation failed</p><ul className="list-disc pl-5 text-sm">{validation.errors.map((e, i) => <li key={i}>{e}</li>)}</ul></>}
        {validation.clarification && <><h3 className="font-medium">Clarification required</h3><ol className="list-decimal pl-5 text-sm">{validation.clarification.questions.map((q, i) => <li key={i}>{q}</li>)}</ol>{validation.clarification.unsupported.length > 0 && <><p className="font-medium">Unsupported requirements</p><ul className="list-disc pl-5 text-sm">{validation.clarification.unsupported.map((q, i) => <li key={i}>{q}</li>)}</ul></>}<p className="text-sm text-ink-3">Answer these in your external AI conversation, then paste its next response. No permissions have changed.</p></>}
      </div>}
    </Sheet>
    {validation?.valid && preview && <Sheet className="space-y-4 px-5 py-4">
      <h2 className="text-heading">3. Permission preview matrix</h2>
      <p className="text-sm text-ink-3">{preview.semantics} Preview expires {validation.expiresAt ? new Date(validation.expiresAt).toLocaleString() : "soon"}. Changes to roles or the catalog require a fresh preview.</p>
      {preview.warnings.length > 0 && <div className="rounded-lg border border-amber-300 bg-amber-50 p-3"><h3 className="font-medium">Review these risks before confirming</h3><ul className="mt-2 list-disc pl-5 text-sm">{preview.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></div>}
      {preview.roles.map((role, i) => <section key={role.id ?? `new-${i}`} className="space-y-3">
        <h3 className="font-semibold">{role.name} - {role.operation} ({role.holders} current holders)</h3>
        <div className="overflow-x-auto rounded-lg border border-rule"><table className="w-full text-left text-sm"><thead><tr className="border-b border-rule bg-bench">{["App", "Resource", "Category", "Action / permission", "Before", "After", "Scope before / after"].map(h => <th key={h} className="p-2 font-medium">{h}</th>)}</tr></thead><tbody>{role.rows.map(row => <tr key={`${row.app}/${row.permission}`} className={`border-b border-rule ${row.before !== row.after ? "bg-amber-50/50" : ""}`}><td className="p-2">{row.app}</td><td className="p-2">{row.resource}</td><td className="p-2">{row.category}</td><td className="p-2">{row.action}<code className="block text-xs text-ink-3">{row.permission}</code></td><td className="p-2">{row.before ? "Allow" : "Deny"}</td><td className="p-2 font-semibold">{row.after ? "Allow" : "Deny"}</td><td className="p-2">{row.beforeScope ?? "None"} / {row.afterScope ?? "None"}</td></tr>)}</tbody></table>{!role.rows.length && <p className="p-3 text-sm">No permission grants. Omitted access is denied.</p>}</div>
        <details className="text-sm"><summary className="cursor-pointer">Scopes, workflow abilities, limits and description changes</summary><pre className="mt-2 overflow-x-auto rounded bg-bench p-3 text-xs">{JSON.stringify({ before: { scopes: role.beforeScopes, abilities: role.beforeAbilities, description: role.beforeDescription }, after: { scopes: role.afterScopes, abilities: role.afterAbilities, description: role.afterDescription } }, null, 2)}</pre></details>
      </section>)}
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} disabled={pending} onChange={e => setConfirmed(e.target.checked)} className="mt-1" /><span>I have reviewed all role changes, revoked access, scopes, workflow authorities, limits and risks above. I authorize applying these exact policy replacements to this company.</span></label>
      <Button variant="primary" disabled={pending || !confirmed} onClick={apply}>{pending ? "Applying..." : "Confirm & apply reviewed policy"}</Button>
    </Sheet>}
    {error && <p role="alert" className="rounded-lg border border-danger/30 p-3 text-sm text-danger">{error}</p>}
    {applied && <p role="status" className="rounded-lg border border-rule p-3 text-sm">{applied}</p>}
    <Sheet className="space-y-3 px-5 py-4">
      <h2 className="text-heading">Policy version history</h2>
      <p className="text-sm text-ink-3">Applied imports retain the exact policy and before/after snapshots. Download a version for review. Restoring older access requires a new validated import and confirmation.</p>
      {history.length ? <ul className="divide-y divide-rule">{history.map(v => <li key={v.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><span>{new Date(v.appliedAt).toLocaleString()} - {v.actor} - {v.roles} roles<code className="block text-xs text-ink-3">{v.id}</code></span><Button disabled={pending} onClick={() => start(async () => { const result = await downloadPolicyVersion(v.id); if (result.ok) download(`access-policy-version-${v.id}.json`, result.data); else setError(result.error); })}>Download version</Button></li>)}</ul> : <p className="text-sm text-ink-3">No policies have been applied through this importer.</p>}
    </Sheet>
    <details className="rounded-lg border border-rule p-4 text-sm"><summary className="cursor-pointer font-medium">Supported applications, actions, scopes and conditions</summary><p className="mt-3">{context.semantics}</p><pre className="mt-3 max-h-96 overflow-auto rounded bg-bench p-3 text-xs">{JSON.stringify(context.catalog, null, 2)}</pre></details>
  </div>;
}
