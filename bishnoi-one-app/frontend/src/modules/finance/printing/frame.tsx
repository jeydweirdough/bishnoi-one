"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { FinancePrintButton, prepareFinancePrint } from "./print-action";
import { attachmentsReady, clearPrintAttachments } from "./attachments";
import "./print.css";

const FILTER_LABELS: Record<string, string> = {
  start: "From", end: "To", year: "Year", quarter: "Quarter", on: "As of", asOf: "As of",
  book: "Book", list: "List", show: "Status", bucket: "Aging bucket", q: "Search", month: "Month",
};

/** Finance-owned framing only. Every page retains its authoritative document body. */
export function FinancePrintFrame({ org, company, children }: { org: Org | null; company: { name: string; slug: string } | null; children: ReactNode }) {
  const path = usePathname();
  const timestamp = useRef<HTMLSpanElement>(null);
  const context = useRef<HTMLParagraphElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const documentPage = /\/vouchers\/[^/]+\/print$|\/ledger\/voucher\//.test(path) || /\/funds\/[^/]+\/report$/.test(path);
  const existingPrintAction = documentPage || /^\/finance\/invoices\/[^/]+$/.test(path);
  const wide = /\/bir(?:\/|$)|\/bills\/aging|\/ledger\/(accounts|trial-balance)|\/invoices\/receivables/.test(path)
    || /^\/finance\/(bills|suppliers|vouchers|ledger|invoices|bank|funds)$/.test(path);
  const printable = /^\/finance\/(bills|suppliers|vouchers|ledger|invoices|bank|funds|bir)(\/|$)/.test(path)
    && !/\/new(?:\/|$)|\/files(?:\/|$)|\/sales-dat(?:\/|$)|\/ledger\/(posting|categories)(?:\/|$)|\/invoices\/series(?:\/|$)/.test(path);

  useEffect(() => {
    const prepare = () => {
      if (root.current) root.current.dataset.attachmentsPending = String(!attachmentsReady(root.current));
      if (timestamp.current) timestamp.current.textContent = "Printed " + new Intl.DateTimeFormat(org?.locale ?? "en-PH", {
        dateStyle: "medium", timeStyle: "short", timeZone: org?.timezone ?? "Asia/Manila",
      }).format(new Date());
      const values = new Map<string, string>();
      const query = new URLSearchParams(window.location.search);
      query.forEach((value, name) => { if (FILTER_LABELS[name] && value) values.set(name, value); });
      root.current?.querySelectorAll<HTMLInputElement | HTMLSelectElement>("form input[name], form select[name]").forEach((field) => {
        if (!FILTER_LABELS[field.name]) return;
        // Print applied server-rendered filters, not unsent edits to the filter form.
        const value = field instanceof HTMLSelectElement
          ? (Array.from(field.options).find(option => option.defaultSelected) ?? field.options[0])?.textContent?.trim()
          : field.defaultValue;
        if (value) values.set(field.name, value);
      });
      if (context.current) context.current.textContent = Array.from(values, ([name, value]) => `${FILTER_LABELS[name]}: ${value}`).join(" · ");
      if (root.current) root.current.dataset.editing = String(query.has("edit") || /\/new(?:\/|$)/.test(path));
    };
    prepare();
    window.addEventListener("beforeprint", prepare);
    const element = root.current;
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "p" && printable) {
        event.preventDefault();
        void prepareFinancePrint().catch(error => window.alert(error instanceof Error ? error.message : "Unable to prepare print."));
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => { window.removeEventListener("beforeprint", prepare); window.removeEventListener("keydown", shortcut); if (element) clearPrintAttachments(element); };
  }, [org?.locale, org?.timezone, path]);

  return <div ref={root} className="finance-print-scope" data-print-layout={wide ? "landscape" : "portrait"} data-print-supported={String(printable)}>
    {printable && !existingPrintAction && <div className="finance-print-toolbar print:hidden">
      <FinancePrintButton label="Print / Save as PDF" />
    </div>}
    <div className="finance-print-banner" aria-hidden="true">
      <div className="finance-print-company">
        {company?.slug === "2mg" && <div className="finance-print-company-logo">
          {/* Original user-supplied image; only its surrounding white space is framed. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/finance/brand/2mg-logo.jpg" alt="2MG Inc." width={200} height={200} loading="eager" />
        </div>}
        {company?.slug !== "2mg" && <div><p className="finance-print-company-name">{company?.name ?? org?.name ?? "Finance"}</p><p className="finance-print-department">Finance documents &amp; reports</p></div>}
      </div>
      <div className="finance-print-system">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/finance/brand/bishnoi-one-mark.png" alt="" width={48} height={48} loading="eager" />
        <div><strong>BISHNOI ONE</strong><span>Finance workspace</span></div>
      </div>
    </div>
    <p ref={context} className="finance-print-context" aria-hidden="true" />
    <p className="finance-print-editing">Editing view — review and save the record before printing its document.</p>
    <p className="finance-print-attachment-warning">Attachments have not been prepared. Cancel this print and use Print / Save as PDF to include their pages.</p>
    <div className="finance-print-content">{children}</div>
    <div className="finance-print-attachments" />
    <footer className="finance-print-footer" aria-hidden="true">
      <span>Bishnoi One · Finance document</span><span ref={timestamp}>Print copy</span>
    </footer>
  </div>;
}
