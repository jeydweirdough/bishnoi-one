// The Admin Console Home's Export: every figure on the page for the chosen period, as a CSV file.
import { NextResponse, type NextRequest } from "next/server";
import { toCsv } from "@/src/platform/lib/csv";
import { loadOverview } from "@/src/one/home/overview";
import { PERIODS, periodOf } from "@/src/one/home/periods";

export async function GET(request: NextRequest) {
  const period = periodOf(request.nextUrl.searchParams.get("period"));
  const label = PERIODS.find((p) => p.value === period)!.label;
  let o;
  try {
    o = await loadOverview(period);
  } catch (error) {
    return new NextResponse(error instanceof Error ? error.message : "The figures couldn't be loaded.", { status: 502 });
  }
  const rows: (string | number)[][] = [
    ["Section", "Figure", label, "Period before"],
    ["Activity", "People who signed in", o.period.now.signedIn, o.period.before.signedIn],
    ["Activity", "Wrong passwords", o.period.now.failed, o.period.before.failed],
    ["Activity", "People added", o.period.now.added, o.period.before.added],
    ["People", "Active", o.people.active, ""],
    ["People", "Switched off", o.people.off, ""],
    ["People", "In the recycle bin", o.people.inBin, ""],
    ["People", "Administrators", o.people.administrators, ""],
    ["Security", "Administrators with two-step sign-in", `${o.security.twoStepAdministrators.on} of ${o.security.twoStepAdministrators.of}`, ""],
    ["Security", "Everyone with two-step sign-in", `${o.security.twoStepEveryone.on} of ${o.security.twoStepEveryone.of}`, ""],
    ["Waiting on you", "No role yet", o.people.noRole, ""],
    ["Waiting on you", "No apps yet", o.people.noApps, ""],
    ["Waiting on you", "Invitations waiting", o.signIns.invitesPending, ""],
    ["Waiting on you", "Passwords to change", o.signIns.passwordsToChange, ""],
    ["Waiting on you", "Locked out now", o.security.lockedNow, ""],
    ["Waiting on you", "Emails to change", o.security.offDomain, ""],
    ...o.apps.map((a) => ["Access by app", a.name, a.people, ""]),
    ...o.roles.map((r) => ["People by role", r.name, r.people, ""]),
    [],
    ["Month", "People who signed in", "Wrong passwords", "People added"],
    ...o.months.map((m) => [m.month, m.signedIn, m.failed, m.added]),
  ];
  return new NextResponse(toCsv(rows), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="admin-console-home-${period}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
