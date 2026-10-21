"use client";

import { ArrowLeftRight, ChevronDown, LogOut, UserRound } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Avatar } from "../ui/avatar";
import { Modal } from "../ui/modal";
import { signOut } from "../actions/session";
import { addressKnown, THIS_APP, appUrl } from "../lib/apps";
import type { Me } from "../lib/types";
import { AppLauncher } from "./app-launcher";

// The top right of every page: the app's bell, if it has one, then who you are.
// The same on a phone, beside the menu button.

/** `bell`: the app's own notifications button. Left out, no bell: a bell that never rings is only noise. */
export function TopActions({ me, bell }: { me: Me; bell?: ReactNode }) {
  return (
    <div className="flex items-center gap-1">
      <AppLauncher />
      {bell}
      <Profile me={me} />
    </div>
  );
}

function Profile({ me }: { me: Me }) {
  const pathname = usePathname();
  const router = useRouter();
  // The menu belongs to the page it was opened on, so navigating closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const [leaving, setLeaving] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpenOn(null);
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpenOn(null);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);
  const switchHref =
    THIS_APP && THIS_APP !== "platform" && addressKnown("platform")
      ? `${appUrl("platform")}/go?app=${THIS_APP}&choose=1&return=${encodeURIComponent(`${appUrl(THIS_APP)}/auth/platform`)}`
      : null;
  function pick(key: string) {
    setOpenOn(null);
    if (key === "account") router.push("/account");
    else if (key === "switch" && switchHref) window.location.href = switchHref;
    else if (key === "signout") setLeaving(true);
  }
  const here = pathname === "/account" || pathname.startsWith("/account/");
  const item = "flex w-full items-center gap-2.5 px-4 py-2 text-left text-sm text-ink hover:bg-bench";
  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpenOn(open ? null : pathname)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Your profile: ${me.user.fullName}`}
        title={me.user.fullName}
        className={`flex h-10 items-center gap-2 rounded-[3px] pr-2 pl-1 transition-colors hover:bg-sheet ${here || open ? "bg-hema-tint" : ""}`}
      >
        <Avatar name={me.user.fullName} id={me.user.id} photoAt={me.user.photoAt} size="sm" />
        <span className="hidden max-w-40 truncate text-sm font-semibold text-ink sm:block">{me.user.fullName}</span>
        <ChevronDown className="hidden size-4 text-ink-3 sm:block" aria-hidden />
      </button>
      {open && (
        <div role="menu" className="absolute top-full right-0 z-40 mt-1 min-w-56 rounded-[3px] border border-rule bg-sheet py-1 shadow-overlay">
          {/* Who you're signed in as, above what you can do about it. */}
          <div className="border-b border-rule px-4 pt-2 pb-3">
            <p className="truncate text-sm font-semibold text-ink">{me.user.fullName}</p>
            <p className="truncate text-meta text-ink-3">{me.user.email}</p>
          </div>
          <button type="button" role="menuitem" className={`${item} mt-1`} onClick={() => pick("account")}>
            <UserRound className="size-4 text-ink-3" aria-hidden />
            Your profile
          </button>
          {/* Each company has its own data here. Someone who works for more than one
              picks the other on Bishnoi One, which sends them back signed in there. */}
          {switchHref && (
            <button type="button" role="menuitem" className={item} onClick={() => pick("switch")}>
              <ArrowLeftRight className="size-4 text-ink-3" aria-hidden />
              Switch company
            </button>
          )}
          <div className="my-1 border-t border-rule" />
          <button type="button" role="menuitem" className={item} onClick={() => pick("signout")}>
            <LogOut className="size-4 text-ink-3" aria-hidden />
            Sign out
          </button>
        </div>
      )}
      <SignOutDialog open={leaving} onClose={() => setLeaving(false)} />
    </div>
  );
}

/** "Sign out?": the one confirmation, wherever signing out starts. */
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
      <p className="mt-2 text-sm text-ink-2">You&apos;ll need your email and password to get back in.</p>
    </Modal>
  );
}
