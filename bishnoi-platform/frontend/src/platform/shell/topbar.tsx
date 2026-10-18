"use client";

import { ArrowLeftRight, Bell, ChevronDown, LogOut, Mail, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Dropdown, Modal, Popover, type MenuProps } from "antd";
import { Suspense, use, useState, type ReactNode } from "react";
import { Avatar } from "../ui/avatar";
import { signOut } from "../actions/session";
import { addressKnown, THIS_APP, appUrl } from "../lib/apps";
import type { Me } from "../lib/types";

// The top right of every page: the notification bell, then who you are.
// The same two on a phone, beside the menu button.

/** One notification: what, why, and where it's dealt with. */
export type Notification = { key: string; title: string; reason?: string; href: string };

/** `notifications`: the app's own (the CRM's are its attention prompts), still
 *  loading when the page is drawn so nothing waits for them. Left out, no bell:
 *  a bell that never rings is only noise. */
export function TopActions({ me, notifications, allHref, bell }: { me: Me; notifications?: Promise<Notification[]>; allHref?: string; bell?: ReactNode }) {
  return (
    <div className="flex items-center gap-1">
      {/* An app's own bell (Inventory's alerts), or the shared one fed its notifications. */}
      {bell}
      {!bell && notifications && (
        <Suspense fallback={<BellButton count={0} />}>
          <LoadedBell notifications={notifications} allHref={allHref} />
        </Suspense>
      )}
      <Profile me={me} />
    </div>
  );
}

function BellButton({ count, open = false }: { count: number; open?: boolean }) {
  return (
    <button
      type="button"
      aria-label={count ? `Notifications: ${count}` : "Notifications"}
      title="Notifications"
      className={`relative grid size-10 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sheet hover:text-ink ${open ? "bg-sheet text-ink" : ""}`}
    >
      <Bell className="size-5" aria-hidden />
      {count > 0 && (
        <span className="absolute top-1 right-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[0.625rem] leading-none font-semibold text-white tabular-nums ring-2 ring-bench" aria-hidden>
          {count > 9 ? "9+" : count}
        </span>
      )}
    </button>
  );
}

function LoadedBell({ notifications, allHref }: { notifications: Promise<Notification[]>; allHref?: string }) {
  const items = use(notifications);
  const pathname = usePathname();
  // The list belongs to the page it was opened on, so navigating closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const close = () => setOpenOn(null);
  const list = (
    <div className="w-[min(22rem,calc(100vw-2rem))]">
      <div className="flex items-center justify-between gap-3 border-b border-rule px-4 py-3">
        <p className="font-semibold text-ink">Notifications</p>
        {allHref && items.length > 0 && (
          <Link href={allHref} onClick={close} className="text-meta font-medium text-ink hover:underline">
            See all
          </Link>
        )}
      </div>
      {items.length === 0 ? (
        <div className="px-4 py-8 text-center">
          <Bell className="mx-auto size-6 text-ink-3" aria-hidden />
          <p className="mt-2 text-sm font-semibold text-ink">No pending items</p>
          <p className="mt-0.5 text-meta text-ink-3">Overdue follow-ups, pending quotes and similar items appear here.</p>
        </div>
      ) : (
        <ul className="max-h-[min(24rem,60dvh)] divide-y divide-rule overflow-y-auto">
          {items.map((n) => (
            <li key={n.key}>
              <Link href={n.href} onClick={close} className="block px-4 py-3 hover:bg-sheet">
                <span className="block text-sm font-semibold text-ink">{n.title}</span>
                {n.reason && <span className="mt-0.5 block text-meta text-ink-3">{n.reason}</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
  return (
    <Popover
      content={list}
      trigger="click"
      placement="bottomRight"
      arrow={false}
      open={open}
      onOpenChange={(o) => setOpenOn(o ? pathname : null)}
      styles={{ container: { padding: 0 } }}
    >
      <span className="inline-flex">
        <BellButton count={items.length} open={open} />
      </span>
    </Popover>
  );
}

function Profile({ me }: { me: Me }) {
  const pathname = usePathname();
  const router = useRouter();
  const [leaving, setLeaving] = useState(false);
  const switchHref =
    THIS_APP && THIS_APP !== "platform" && addressKnown("platform")
      ? `${appUrl("platform")}/go?app=${THIS_APP}&return=${encodeURIComponent(`${appUrl(THIS_APP)}/auth/platform`)}`
      : null;
  const items: MenuProps["items"] = [
    { key: "account", label: "Your profile", icon: <UserRound className="size-4" aria-hidden /> },
    // The CRM sends email from each person's own mailbox.
    ...(process.env.NEXT_PUBLIC_BISHNOI_APP === "crm" ? [{ key: "mailbox", label: "Mailbox", icon: <Mail className="size-4" aria-hidden /> }] : []),
    // Each company has its own data here. Someone who works for more than one
    // picks the other on Bishnoi One, which sends them back signed in there.
    ...(switchHref ? [{ key: "switch", label: "Switch company", icon: <ArrowLeftRight className="size-4" aria-hidden /> }] : []),
    { type: "divider" as const },
    { key: "signout", label: "Sign out", icon: <LogOut className="size-4" aria-hidden /> },
  ];
  function pick({ key }: { key: string }) {
    if (key === "account") router.push("/account");
    else if (key === "mailbox") router.push("/account/mailbox");
    else if (key === "switch" && switchHref) window.location.href = switchHref;
    else if (key === "signout") setLeaving(true);
  }
  const here = pathname === "/account" || pathname.startsWith("/account/");
  return (
    <>
      <Dropdown
        menu={{ items, onClick: pick }}
        trigger={["click"]}
        placement="bottomRight"
        popupRender={(menu) => (
          <div className="min-w-56 rounded-lg border border-rule bg-bench shadow-lg">
            {/* Who you're signed in as, above what you can do about it. */}
            <div className="border-b border-rule px-4 py-3">
              <p className="truncate text-sm font-semibold text-ink">{me.user.fullName}</p>
              <p className="truncate text-meta text-ink-3">{me.user.email}</p>
            </div>
            <div className="[&_.ant-dropdown-menu]:!shadow-none">{menu}</div>
          </div>
        )}
      >
        <button
          type="button"
          aria-label={`Your profile: ${me.user.fullName}`}
          title={me.user.fullName}
          className={`flex h-10 items-center gap-2 rounded-lg pr-2 pl-1 transition-colors hover:bg-sheet ${here ? "bg-hema-tint" : ""}`}
        >
          <Avatar name={me.user.fullName} id={me.user.id} photoAt={me.user.photoAt} size="sm" />
          <span className="hidden max-w-40 truncate text-sm font-semibold text-ink sm:block">{me.user.fullName}</span>
          <ChevronDown className="hidden size-4 text-ink-3 sm:block" aria-hidden />
        </button>
      </Dropdown>
      <SignOutDialog open={leaving} onClose={() => setLeaving(false)} />
    </>
  );
}

/** "Sign out?": the one confirmation, wherever signing out starts (the profile menu, the sidebar's foot). */
export function SignOutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [pending, setPending] = useState(false);
  return (
    <Modal
      open={open}
      title="Sign out?"
      okText="Sign out"
      cancelText="Cancel"
      confirmLoading={pending}
      onCancel={() => !pending && onClose()}
      onOk={async () => {
        setPending(true);
        await signOut();
      }}
      width={400}
    >
      You&apos;ll need your email and password to get back in.
    </Modal>
  );
}
