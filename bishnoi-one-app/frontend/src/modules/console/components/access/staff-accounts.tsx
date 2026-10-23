// The staff who sign in to this console, by role, with what a Platform Admin
// does to each: shown under Users → Staff and Access → Roles & permissions alike.
import { Empty, SectionTitle, Sheet } from "@/src/modules/console/platform/ui/sheet";
import { getMe, load } from "@/src/modules/console/platform/lib/api";
import { Count } from "@/src/modules/console/components/marks";
import { SuspendedTag } from "@/src/modules/console/components/organizations/record-tools";
import type { Roles } from "@/src/modules/console/lib/types";
import { ago, plural } from "@/src/modules/console/lib/words";
import { StaffControls } from "@/src/modules/console/components/access/staff-controls";
import { StaffForm } from "@/src/modules/console/components/access/staff-form";

export async function StaffAccounts({ canChange }: { canChange: boolean }) {
  const [roles, me] = await Promise.all([load<Roles>("/platform/access/roles"), getMe()]);
  return (
  <div className="space-y-5">
    {canChange && (
      <div className="flex items-center justify-between gap-3">
        <p className="text-meta text-ink-3">The staff who sign in to this console.</p>
        <StaffForm />
      </div>
    )}
    {roles.staffRoles.map((r) => (
      <Sheet key={r.role}>
        <div className="px-5 pt-4 pb-2">
          <SectionTitle icon={r.role === "admin" ? "roles" : "support"}>
            {r.role === "admin" ? "Platform Admins" : "Support"}
            <Count n={r.holders.length} />
          </SectionTitle>
        </div>
        {r.holders.length === 0 ? (
          <Empty title={`No ${r.name} accounts yet`} icon="person">
            {r.role === "admin" ? "Make a Support member a Platform Admin below, or add one with Add staff." : canChange ? "Add one with Add staff above." : "A Platform Admin adds staff."}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule border-t border-rule" role="list">
            {r.holders.map((s) => {
              const self = s.id === me.user.id;
              return (
                <li key={s.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                  <span className="min-w-0 flex-1 basis-56">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className={`font-semibold ${s.isActive ? "text-ink" : "text-ink-3"}`}>{s.fullName}</span>
                      {self && <span className="rounded-full bg-hema-tint px-1.5 text-stamp text-hema uppercase">You</span>}
                      {!s.isActive && <SuspendedTag label="Inactive" />}
                    </span>
                    <span className="block truncate text-meta text-ink-3">
                      {s.no ? `No. ${s.no} · ` : ""}
                      {s.email} · last signed in {ago(s.lastSignInAt)}
                      {s.activeSessions > 0 && ` · ${plural(s.activeSessions, "session")} open`}
                    </span>
                  </span>
                  {canChange &&
                    (self ? (
                      <span className="text-meta text-ink-3">Another Platform Admin changes your account.</span>
                    ) : (
                      <StaffControls person={s} />
                    ))}
                </li>
              );
            })}
          </ul>
        )}
      </Sheet>
    ))}
  </div>
  );
}
