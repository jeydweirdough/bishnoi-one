"use client";

import { Input, InputNumber, Select, Tag } from "antd";
import { Mail } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { FormError } from "@/src/platform/ui/field";
import { Sheet } from "@/src/platform/ui/sheet";
import { connectSmtp, disconnectMailbox, makeDefaultMailbox, startMailbox, type MailboxInfo } from "../../actions/mailbox";

/** Account → Mailbox: connect your own mailbox, so emails from the CRM go out from your address. */
export function MailboxPanel({ info }: { info: MailboxInfo }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [smtp, setSmtp] = useState({ address: "", host: "", port: 587, security: "starttls" as "starttls" | "ssl" | "none", username: "", password: "" });

  function signIn(key: "gmail" | "outlook" | "zoho_mail") {
    start(async () => {
      const r = await startMailbox(key);
      if (!r.ok) return setError(r.error);
      window.location.href = r.data.url;
    });
  }

  const boxes = info.mailboxes;
  return (
    <div className="max-w-2xl space-y-4">
      {boxes.length > 0 && (
        <Sheet>
          <ul className="divide-y divide-rule">
            {boxes.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                <span className="grid size-10 place-items-center rounded-full bg-bench text-ink-2">
                  <Mail className="size-5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">{m.address}</p>
                  <p className="text-meta text-ink-3">
                    {m.providerName}
                    {m.lastError && <span className="text-danger"> · Last time: {m.lastError}</span>}
                  </p>
                </div>
                {m.isDefault ? <Tag color="processing">Default</Tag> : <Tag color={m.lastError ? "error" : "success"}>{m.lastError ? "Needs attention" : "Working"}</Tag>}
                {!m.isDefault && (
                  <Button size="sm" disabled={pending} onClick={() => start(async () => void (await makeDefaultMailbox(m.id)))}>
                    Make default
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="quiet"
                  disabled={pending}
                  onClick={() =>
                    start(async () => {
                      const r = await disconnectMailbox(m.id);
                      if (r.ok) toast.success("Mailbox disconnected", { description: m.address });
                      else toast.error(r.error);
                    })
                  }
                >
                  Disconnect
                </Button>
              </li>
            ))}
          </ul>
          <p className="border-t border-rule px-5 py-2.5 text-meta text-ink-3">Each email goes from the one you pick in From; the default unless you pick another.</p>
        </Sheet>
      )}
      <Sheet className="px-5 py-5">
        <p className="font-semibold text-ink">{boxes.length ? "Add another: sign in with your provider" : "Sign in with your provider"}</p>
        <p className="mt-1 text-meta text-ink-3">You&apos;ll be asked to allow the CRM to send email for you. It only sends; it never reads your mail.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {info.providers.map((p) => (
            <Button key={p.key} onClick={() => signIn(p.key)} disabled={!p.ready || pending} title={p.ready ? undefined : "An administrator sets it up first, in Settings → Connections"}>
              {p.name}
            </Button>
          ))}
        </div>
        {info.providers.every((p) => !p.ready) && (
          <p className="mt-3 text-meta text-ink-3">None is set up for the company yet: an administrator sets them up in Settings → Connections. Meanwhile, any mailbox works by SMTP below.</p>
        )}
      </Sheet>
      <Sheet className="px-5 py-5">
        <p className="font-semibold text-ink">Or any other provider, by SMTP</p>
        <p className="mt-1 text-meta text-ink-3">Your provider&apos;s help pages give the server and port. Some ask for an app password instead of your usual one.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-sm text-ink">Your email address</span>
            <Input value={smtp.address} onChange={(e) => setSmtp({ ...smtp, address: e.target.value })} />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-ink">Server</span>
            <Input value={smtp.host} onChange={(e) => setSmtp({ ...smtp, host: e.target.value })} placeholder="smtp.example.com" />
          </label>
          <div className="flex gap-3">
            <label className="block">
              <span className="mb-1 block text-sm text-ink">Port</span>
              <InputNumber min={1} max={65535} value={smtp.port} onChange={(v) => setSmtp({ ...smtp, port: v ?? 587 })} />
            </label>
            <label className="block flex-1">
              <span className="mb-1 block text-sm text-ink">Security</span>
              <Select
                className="w-full"
                value={smtp.security}
                onChange={(security) => setSmtp({ ...smtp, security })}
                options={[
                  { value: "starttls", label: "STARTTLS (587)" },
                  { value: "ssl", label: "SSL (465)" },
                  { value: "none", label: "None" },
                ]}
              />
            </label>
          </div>
          <label className="block">
            <span className="mb-1 block text-sm text-ink">User name</span>
            <Input value={smtp.username} onChange={(e) => setSmtp({ ...smtp, username: e.target.value })} autoComplete="off" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-ink">Password</span>
            <Input.Password value={smtp.password} onChange={(e) => setSmtp({ ...smtp, password: e.target.value })} autoComplete="new-password" />
          </label>
        </div>
        <FormError message={error} />
        <div className="mt-4">
          <Button
            variant="primary"
            loading={pending}
            disabled={!smtp.address || !smtp.host || !smtp.username || !smtp.password}
            onClick={() =>
              start(async () => {
                const r = await connectSmtp(smtp);
                if (!r.ok) return setError(r.fields?.host ?? r.error);
                toast.success("Mailbox connected");
              })
            }
          >
            Connect
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
