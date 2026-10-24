import { notFound } from "next/navigation";
import { getAccount } from "@/src/platform/lib/account";
import { MODULES } from "@/src/platform/lib/modules";
import { LinkButton } from "@/src/platform/ui/ant-button";
import { buttonClass } from "@/src/platform/ui/button";
import { myModules } from "@/src/one/mine";
import { PlainFrame } from "@/src/one/plain-frame";

/**
 * A module's address before its screens are here (decided 2026-10-23). A module
 * brought in gets its own folder (app/(app)/crm/...), which Next serves ahead of
 * this. Until then: one still moving in points to its current app; one not
 * built yet says it's coming; one this person doesn't have says so.
 */
export default async function ModuleNotHereYet({ params }: { params: Promise<{ module: string }> }) {
  const { module: segment } = await params;
  const m = MODULES.find((x) => x.path === `/${segment}`);
  if (!m) notFound();
  const me = await getAccount();
  const mine = myModules(me).find((x) => x.key === m.key);

  let title: string;
  let line: string;
  let action: React.ReactNode = null;
  if (!mine) {
    title = `Your account doesn't include ${m.label}`;
    line = "Ask your company's administrator to give it to you, if you need it.";
  } else if (m.status === "soon") {
    title = `${m.label} is coming soon`;
    line = `${m.label} is being built as part of Bishnoi One. It will appear here when it's ready.`;
  } else {
    title = `${m.label} is moving into Bishnoi One`;
    line = `Until it's here, ${m.label} opens in its current app, signed in with the same account.`;
    if (mine.oldUrl)
      action = (
        <a href={mine.oldUrl} className={buttonClass("primary", "md", "mt-6")}>
          Open {m.label}
        </a>
      );
  }

  return (
    <PlainFrame>
    <main className="mx-auto max-w-[90rem] px-4 py-16 sm:px-6">
      <div className="mx-auto max-w-lg rounded-2xl border border-rule bg-white px-6 py-12 text-center">
        <span className="mx-auto grid size-14 place-items-center rounded-2xl" style={{ background: m.tint, color: m.ink }}>
          <m.icon className="size-7" aria-hidden />
        </span>
        <h1 className="mt-5 text-xl font-semibold text-ink">{title}</h1>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-ink-2">{line}</p>
        {action}
        <div className="mt-6">
          <LinkButton href="/" variant="quiet">
            Back to all modules
          </LinkButton>
        </div>
      </div>
    </main>
    </PlainFrame>
  );
}
