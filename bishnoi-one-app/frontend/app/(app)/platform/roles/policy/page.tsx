import { accountSend } from "@/src/platform/lib/account";
import { ApiError } from "@/src/platform/lib/api";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { PolicyExchange } from "@/src/one/access/policy-exchange";
import type { PolicyContext, PolicyVersion } from "@/src/one/access/policy-types";
export const metadata = { title: "AI-assisted access import / export" };

export default async function AccessPolicyPage() {
  const heading = <PageHeader title="Access import / export" crumbs={[{ href: "/platform/roles", label: "Roles" }]}>Prepare an external-AI prompt, resolve questions, validate a policy, then review and confirm its application.</PageHeader>;
  let context: PolicyContext;
  let history: PolicyVersion[];
  try {
    [context, history] = await Promise.all([
      accountSend<PolicyContext>("GET", "/identity/access/policy/context"),
      accountSend<PolicyVersion[]>("GET", "/identity/access/policy/history"),
    ]);
  } catch (error) {
    return <>{heading}<Sheet className="p-5"><p>{error instanceof ApiError && error.status === 403 ? error.message : "Access policies could not be loaded. Check your sign-in and connection, then refresh."}</p></Sheet></>;
  }
  return <>{heading}<PolicyExchange context={context} initialHistory={history} /></>;
}
