import { accountSend } from "@/src/platform/lib/account";
import { ApiError } from "@/src/platform/lib/api";
import { toCsv } from "@/src/platform/lib/csv";
import type { AccessData } from "@/src/one/access/types";

// People as a CSV file (2026-10-30), for the company's administrators: the same columns the import reads,
// so a file exported, edited and imported again adds who's new.
export async function GET() {
  let data: AccessData;
  try {
    data = await accountSend<AccessData>("GET", "/identity/access");
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 503;
    return new Response(error instanceof Error ? error.message : "People couldn't be read.", { status });
  }
  const roles = Object.fromEntries(data.roles.map((r) => [r.id, r.name]));
  const apps = Object.fromEntries(data.modules.map((m) => [m.key, m.name]));
  const rows = [
    ["Name", "Email", "Title", "Role", "Apps", "Status", "Company administrator"],
    ...data.people.map((p) => [
      p.fullName,
      p.email,
      p.title ?? "",
      p.roleId ? (roles[p.roleId] ?? "") : "",
      p.apps.map((a) => apps[a.key] ?? a.key).join("; "),
      p.status === "active" ? "Active" : "Switched off",
      p.isCompanyAdmin ? "Yes" : "",
    ]),
  ];
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date());
  const slug = data.company.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return new Response(toCsv(rows), {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${slug || "people"}-people-${day}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
