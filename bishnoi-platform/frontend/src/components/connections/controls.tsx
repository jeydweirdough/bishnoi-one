"use client";

import { Check, Copy, KeyRound, Link2, Power, RefreshCw, Trash2, Unplug } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { addLink, disconnectApp, makeConnectKey, newLinkKey, removeLink, switchLink } from "@/src/actions/connections";

// The switchboard's buttons. Platform Admins only; the page doesn't show them otherwise.

/** The key, shown once, with where it goes. */
function ShowKey({ appName, appKey, value, onHide }: { appName: string; appKey: string; value: string; onHide: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-2 w-full rounded-[14px] border border-rule-strong bg-sheet px-4 py-3 text-sm">
      <p className="font-semibold">{appName}&apos;s connect key. It&apos;s shown this once.</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 rounded-[8px] bg-bench px-2 py-1.5 font-mono text-meta break-all">{value}</code>
        <Button
          size="sm"
          icon={copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(value);
              setCopied(true);
            } catch {
              toast.error("Couldn't copy. Select the key and press Ctrl+C.");
            }
          }}
        >
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-meta text-ink-2">
        <li>
          On {appName}&apos;s server, set <code className="font-mono">PLATFORM_APP_KEY</code> to it: in <code className="font-mono">bishnoi-{appKey}/backend/.env</code> on a computer, or in its API&apos;s Vercel project settings online.
        </li>
        <li>Restart {appName}, or deploy it again. It connects within a minute, and this page says so.</li>
      </ol>
      <button type="button" onClick={onHide} className="mt-2 text-meta text-ink-3 hover:text-ink hover:underline">
        Done, hide it
      </button>
    </div>
  );
}

/**
 * Makes an application's connect key and shows it once. A new one replaces
 * the old: the application stops connecting until its server has the new one.
 */
export function ConnectKey({ appId, appName, appKey, has }: { appId: string; appName: string; appKey: string; has: boolean }) {
  const [key, setKey] = useState<string | null>(null);
  const [pending, start] = useTransition();

  if (key) return <ShowKey appName={appName} appKey={appKey} value={key} onHide={() => setKey(null)} />;
  if (!has) {
    return (
      <Button
        size="sm"
        variant="primary"
        loading={pending}
        icon={<KeyRound className="size-4" aria-hidden />}
        onClick={() =>
          start(async () => {
            const r = await makeConnectKey(appId);
            if (!r.ok) return void toast.error(r.error);
            setKey(r.data.key);
          })
        }
      >
        Make its connect key
      </Button>
    );
  }
  return (
    <ConfirmButton
      label="New key"
      icon={<KeyRound className="size-4" aria-hidden />}
      triggerSize="sm"
      title={`Make a new connect key for ${appName}?`}
      body={`The old key stops working at once: ${appName} can't reach its links until its server has the new one. Do this if the old key may have been seen by someone it shouldn't.`}
      confirmLabel="Make a new key"
      onConfirm={async () => {
        const r = await makeConnectKey(appId);
        if (!r.ok) {
          toast.error(r.error);
          return false;
        }
        setKey(r.data.key);
      }}
    />
  );
}

export function Disconnect({ appId, appName }: { appId: string; appName: string }) {
  return (
    <ConfirmButton
      label={<span className="sr-only">Disconnect {appName}</span>}
      icon={<Unplug className="size-4" aria-hidden />}
      triggerTitle={`Disconnect ${appName}`}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName="!size-8 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
      title={`Disconnect ${appName}?`}
      body="Its connect key stops working, and within 5 minutes it drops every link: what it uses, and what uses it. Its own screens keep working."
      confirmLabel="Disconnect it"
      danger
      onConfirm={async () => {
        const r = await disconnectApp(appId);
        if (!r.ok) {
          toast.error(r.error);
          return false;
        }
        toast.success(`${appName} disconnected`);
      }}
    />
  );
}

export function LinkThem({ fromId, toId, label }: { fromId: string; toId: string; label: string }) {
  const [pending, start] = useTransition();
  return (
    <Button
      size="sm"
      loading={pending}
      icon={<Link2 className="size-4" aria-hidden />}
      onClick={() =>
        start(async () => {
          const r = await addLink(fromId, toId);
          if (!r.ok) return void toast.error(r.error);
          toast.success("Linked", { description: `${label}. Both pick it up within 5 minutes.` });
        })
      }
    >
      Link them
    </Button>
  );
}

export function LinkSwitch({ id, isOn, label }: { id: string; isOn: boolean; label: string }) {
  const [pending, start] = useTransition();
  return (
    <Button
      size="sm"
      variant={isOn ? "default" : "primary"}
      loading={pending}
      icon={<Power className="size-4" aria-hidden />}
      onClick={() =>
        start(async () => {
          const r = await switchLink(id, !isOn);
          if (!r.ok) return void toast.error(r.error);
          toast.success(isOn ? "Switched off" : "Switched on", { description: `${label}. Both pick it up within 5 minutes.` });
        })
      }
    >
      {isOn ? "Switch off" : "Switch on"}
    </Button>
  );
}

export function NewLinkKey({ id, label }: { id: string; label: string }) {
  return (
    <ConfirmButton
      label={<span className="sr-only">New key for {label}</span>}
      icon={<RefreshCw className="size-4" aria-hidden />}
      triggerTitle="Make a new key between them"
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName="!size-8 !px-0 !text-ink-3"
      title="Make a new key between them?"
      body="Both applications pick the new key up within 5 minutes; until both have it, calls between them may be refused. Nothing needs changing on either server."
      confirmLabel="Make a new key"
      onConfirm={async () => {
        const r = await newLinkKey(id);
        if (!r.ok) {
          toast.error(r.error);
          return false;
        }
        toast.success("New key made", { description: label });
      }}
    />
  );
}

export function RemoveLink({ id, label }: { id: string; label: string }) {
  return (
    <ConfirmButton
      label={<span className="sr-only">Remove {label}</span>}
      icon={<Trash2 className="size-4" aria-hidden />}
      triggerTitle={`Remove: ${label}`}
      triggerVariant="quiet"
      triggerSize="sm"
      triggerClassName="!size-8 !px-0 !text-ink-3 hover:!bg-danger/10 hover:!text-danger"
      title={`Remove the link "${label}"?`}
      body="Both applications drop it within 5 minutes. To pause it instead, switch it off: switching it back on keeps the same key."
      confirmLabel="Remove it"
      danger
      onConfirm={async () => {
        const r = await removeLink(id);
        if (!r.ok) {
          toast.error(r.error);
          return false;
        }
        toast.success("Link removed", { description: label });
      }}
    />
  );
}
