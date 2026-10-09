"use client";

import { ArrowLeft, ExternalLink, Mail } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, TextButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { connectSmtp, detectMailbox, disconnectMailbox, makeDefaultMailbox, startMailbox, type MailboxDetect, type MailboxInfo } from "../../actions/mailbox";

/**
 * Account → Mailbox: connect your own mailbox, so emails from the CRM go out
 * from your address. One field first, your email; the CRM works out the
 * provider from it (app/mailbox.py detect), then asks for only what's left:
 * a sign-in button when the company has set one up, else a password, with
 * the steps to make an app password. Server settings only for a provider it
 * doesn't know, and filled in with its best guess.
 */
export function MailboxPanel({ info }: { info: MailboxInfo }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [address, setAddress] = useState("");
  const [found, setFound] = useState<MailboxDetect | null>(null);
  const [password, setPassword] = useState("");
  const [server, setServer] = useState<MailboxDetect["smtp"] | null>(null);
  const [username, setUsername] = useState("");
  const [advanced, setAdvanced] = useState(false);

  function look() {
    setError(null);
    start(async () => {
      const r = await detectMailbox(address.trim());
      if (!r.ok) return setError(r.fields?.address ?? r.error);
      setFound(r.data);
      setServer(r.data.smtp);
      setUsername(r.data.address);
      setPassword("");
      setAdvanced(r.data.provider === null);
    });
  }

  function signIn(key: NonNullable<MailboxDetect["signIn"]>) {
    start(async () => {
      const r = await startMailbox(key);
      if (!r.ok) return setError(r.error);
      window.location.href = r.data.url;
    });
  }

  function connect() {
    if (!found || !server) return;
    setError(null);
    start(async () => {
      const r = await connectSmtp({ address: found.address, host: server.host, port: server.port, security: server.security, username: username || found.address, password });
      if (!r.ok) return setError(r.fields?.host ?? r.fields?.password ?? r.error);
      toast.success("Mailbox connected", { description: found.address });
      setFound(null);
      setAddress("");
      setPassword("");
    });
  }

  const boxes = info.mailboxes;
  return (
    <div className="max-w-2xl space-y-5">
      {boxes.length > 0 && (
        <Sheet>
          <ul className="divide-y divide-rule">
            {boxes.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                <span className="grid size-10 place-items-center rounded-full border-[1.5px] border-ink bg-sage text-ink">
                  <Mail className="size-[18px]" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">{m.address}</p>
                  <p className="text-meta text-ink-3">
                    {m.isDefault ? "Your emails go from here" : m.providerName}
                    {m.lastError && <span className="text-danger"> · Last time: {m.lastError}</span>}
                  </p>
                </div>
                <span
                  className={`inline-flex h-6 items-center rounded-full px-2.5 text-meta font-medium ${
                    m.lastError ? "bg-danger-tint text-danger" : m.isDefault ? "border border-ink text-ink" : "bg-[#e6f2e1] text-[#3f6f35]"
                  }`}
                >
                  {m.lastError ? "Needs attention" : m.isDefault ? "Default" : "Working"}
                </span>
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
        </Sheet>
      )}

      <Sheet className="px-5 pt-4 pb-5">
        {!found ? (
          <>
            <SectionTitle icon="email">{boxes.length ? "Add another mailbox" : "Connect your mailbox"}</SectionTitle>
            <p className="mt-1 text-sm text-ink-3">Type your work email. The CRM only sends from it; it never reads your mail.</p>
            <form
              className="mt-4 flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                look();
              }}
            >
              <div className="min-w-[16rem] flex-1">
                <Field label="Your email" error={error ?? undefined}>
                  {(p) => <Input {...p} type="email" inputMode="email" autoComplete="email" placeholder="you@yourcompany.com" value={address} onChange={(e) => setAddress(e.target.value)} />}
                </Field>
              </div>
              <Button type="submit" variant="primary" loading={pending} disabled={!address.includes("@")}>
                Continue
              </Button>
            </form>
          </>
        ) : (
          <>
            <TextButton onClick={() => setFound(null)} tone="muted" className="mb-3">
              <ArrowLeft className="size-3.5" aria-hidden />
              Another address
            </TextButton>
            <SectionTitle icon="email">{found.address}</SectionTitle>
            <p className="mt-1 text-sm text-ink-3">{found.provider ? `A ${found.name} mailbox.` : "We don't know this provider, so it needs its settings."}</p>

            {found.signIn ? (
              <div className="mt-5">
                <Button variant="primary" loading={pending} onClick={() => signIn(found.signIn!)}>
                  Continue with {found.name}
                </Button>
                <p className="mt-2 text-meta text-ink-3">You&apos;ll sign in to {found.name} and allow the CRM to send email for you. That&apos;s all.</p>
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                {found.help && (
                  <div className="rounded-[18px] bg-mint px-4 py-3">
                    <p className="text-sm font-semibold text-ink">First, make an app password</p>
                    <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-ink-2">
                      {found.help.steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                    <a href={found.help.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-sage-deep hover:underline">
                      Open {found.name}&apos;s app passwords
                      <ExternalLink className="size-3.5" aria-hidden />
                    </a>
                  </div>
                )}
                <Field label={found.help ? "App password" : "Password"} hint={found.help ? "Not your usual password: the one you just made." : undefined}>
                  {(p) => <Input {...p} type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
                </Field>

                {server && (
                  <div>
                    {!found.smtp.guessed && (
                      <TextButton onClick={() => setAdvanced((a) => !a)} aria-expanded={advanced} tone="muted">
                        {advanced ? "Hide the server settings" : `Server settings (already set for ${found.name})`}
                      </TextButton>
                    )}
                    {advanced && (
                      <div className="mt-3 grid gap-3 rounded-[18px] border border-rule px-4 py-4 sm:grid-cols-2">
                        {found.smtp.guessed && <p className="text-meta text-ink-3 sm:col-span-2">Our best guess; your provider&apos;s help pages or your IT give the right ones.</p>}
                        <Field label="Server">{(p) => <Input {...p} value={server.host} onChange={(e) => setServer({ ...server, host: e.target.value })} />}</Field>
                        <div className="grid grid-cols-2 gap-3">
                          <Field label="Port">{(p) => <Input {...p} inputMode="numeric" value={String(server.port)} onChange={(e) => setServer({ ...server, port: Number(e.target.value) || 587 })} />}</Field>
                          <Field label="Security">
                            {(p) => (
                              <Select {...p} value={server.security} onChange={(e) => setServer({ ...server, security: e.target.value as MailboxDetect["smtp"]["security"] })}>
                                <option value="starttls">STARTTLS</option>
                                <option value="ssl">SSL</option>
                                <option value="none">None</option>
                              </Select>
                            )}
                          </Field>
                        </div>
                        <div className="sm:col-span-2">
                          <Field label="User name" hint="Usually your email address.">{(p) => <Input {...p} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="off" />}</Field>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <FormError message={error} />
                <Button variant="primary" loading={pending} disabled={!password} onClick={connect}>
                  Connect mailbox
                </Button>
              </div>
            )}
          </>
        )}
      </Sheet>
    </div>
  );
}
