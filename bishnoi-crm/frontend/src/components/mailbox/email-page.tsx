"use client";

import { SearchInput } from "@/src/platform/ui/field";
import { Segmented } from "antd";
import { PenSquare } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";
import { Button } from "@/src/platform/ui/button";
import { Sheet, Empty } from "@/src/platform/ui/sheet";
import type { ActivityItem } from "@/src/platform/lib/types";
import { sentEmails, type MailboxInfo } from "../../actions/mailbox";
import { Composer } from "./composer";

/** Splits what the CRM kept ("From x (Gmail) to y\n\nThe message") into its parts. */
function parts(a: ActivityItem) {
  const [head, ...rest] = (a.body ?? "").split("\n\n");
  const m = head.match(/^From (.+?) \((.+?)\) to (.+)$/) ?? head.match(/^To ()()(.+)$/);
  return { from: m?.[1] || null, via: m?.[2] || null, to: m?.[3] ?? "", text: m ? rest.join("\n\n") : (a.body ?? "") };
}

/**
 * Email: write to customers from the CRM, through the provider of the mailbox
 * you pick (Zoho Mail, Gmail, Outlook, SMTP), and see what's been sent.
 */
export function EmailPage({ box, initial, teamWide, when }: { box: MailboxInfo; initial: { items: ActivityItem[]; total: number }; teamWide: boolean; when: Record<string, string> }) {
  const [open, setOpen] = useState(false);
  const [who, setWho] = useState<"me" | "all">("me");
  const [q, setQ] = useState("");
  const [list, setList] = useState(initial);
  const [shown, setShown] = useState<string | null>(null);
  const [, start] = useTransition();

  useEffect(() => {
    const t = setTimeout(() => start(async () => setList(await sentEmails(who, q, 0))), q ? 300 : 0);
    return () => clearTimeout(t);
  }, [who, q, open]);

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Button variant="primary" icon={<PenSquare className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
          New email
        </Button>
        {teamWide && (
          <Segmented<"me" | "all">
            value={who}
            onChange={setWho}
            options={[
              { value: "me", label: "Mine" },
              { value: "all", label: "Everyone's" },
            ]}
          />
        )}
        <SearchInput className="max-w-xs" allowClear value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search subject or message" />
        <span className="ml-auto text-meta text-ink-3">
          {box.mailboxes.length ? (
            <>
              Sending from {box.mailboxes.length === 1 ? box.mailboxes[0].address : `${box.mailboxes.length} mailboxes`} ·{" "}
              <Link href="/account/mailbox" className="underline">
                Mailbox
              </Link>
            </>
          ) : (
            <Link href="/account/mailbox" className="underline">
              Connect a mailbox to send
            </Link>
          )}
        </span>
      </div>

      <Sheet>
        <div className="border-b border-rule px-5 py-3">
          <h2 className="text-heading text-ink">Sent</h2>
        </div>
        {list.items.length === 0 ? (
          q ? (
            <Empty icon="email" title="No email matches">Try another name or word.</Empty>
          ) : (
            <Empty
              icon="email"
              title="Nothing sent yet"
              actions={
                <Button variant="primary" icon={<PenSquare className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
                  Write the first email
                </Button>
              }
            >
              Emails sent from the CRM show here and on the customer&apos;s page.
            </Empty>
          )
        ) : (
          <ul className="divide-y divide-rule">
            {list.items.map((a) => {
              const p = parts(a);
              const isOpen = shown === a.id;
              return (
                <li key={a.id}>
                  <button type="button" onClick={() => setShown(isOpen ? null : a.id)} className="grid w-full gap-x-4 px-5 py-3 text-left hover:bg-bench/60 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_auto]">
                    <span className="truncate text-sm text-ink-2">To {p.to}</span>
                    <span className="min-w-0 truncate">
                      <span className="font-medium text-ink">{a.subject}</span>
                      {!isOpen && <span className="text-ink-3"> · {p.text.slice(0, 120)}</span>}
                    </span>
                    <span className="text-meta text-ink-3">{when[a.id] ?? new Date(a.at).toLocaleString("en-PH", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}</span>
                  </button>
                  {isOpen && (
                    <div className="px-5 pb-4">
                      <p className="text-meta text-ink-3">
                        {p.from ? `From ${p.from} through ${p.via}` : "Sent"}
                        {who === "all" && ` · by ${a.owner.name}`}
                        {a.company && (
                          <>
                            {" · "}
                            <Link href={`/companies/${a.company.id}`} className="text-ink underline">
                              {a.company.name}
                            </Link>
                          </>
                        )}
                      </p>
                      <p className="mt-2 whitespace-pre-line text-sm text-ink">{p.text}</p>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {list.total > list.items.length && <p className="border-t border-rule px-5 py-2.5 text-meta text-ink-3">The latest {list.items.length} of {list.total}. Search to find older ones.</p>}
      </Sheet>
      <Composer open={open} onClose={() => setOpen(false)} />
    </>
  );
}
