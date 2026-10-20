// The signed-in frame: the same sidebar every Bishnoi One app wears. A field agent
// also needs their location on while the CRM is open in work hours (a guide
// stands in front of it until it is), and their trail is taken, with a
// marker in the corner saying so.
import type { ReactNode } from "react";
import { ShellLayout } from "@/src/platform/app/shell-layout";
import { getFrame, load } from "@/src/platform/lib/api";
import type { Prompt } from "@/src/actions/attention";
import { FieldTracker } from "@/src/components/field/tracker";
import { CanProvider } from "@/src/components/quick-add/can";
import { isFieldAgent } from "@/src/components/field/words";
import { TermsProvider } from "@/src/components/terms/provider";
import { termsOf } from "@/src/components/terms/terms";
import { CommandMenu, CommandMenuButton, type MenuAction } from "@/src/components/command-menu";
import type { Me } from "@/src/platform/lib/types";

/** The command menu's places and starts: only what this person's role reaches. */
function menuActions(me: Me): MenuAction[] {
  const may = (p: string) => (me.permissions ?? []).includes(p);
  const field = isFieldAgent(me);
  const terms = termsOf(me);
  const all: (MenuAction & { allowed: boolean })[] = [
    { group: "Go to", label: "Home", href: "/", keywords: "dashboard", allowed: true },
    { group: "Go to", label: "Customers", href: "/companies", keywords: "companies accounts", allowed: may("customers.view") },
    { group: "Go to", label: "Contacts", href: "/contacts", keywords: "people", allowed: may("customers.view") },
    { group: "Go to", label: "Lead inbox", href: "/inbox", keywords: "facebook messenger whatsapp viber tawk website enquiries", allowed: may("customers.inbox") },
    { group: "Go to", label: "Find leads with AI", href: "/companies/find", keywords: "chatgpt claude deepseek prospects", allowed: may("customers.create") },
    { group: "Go to", label: "Deals", href: "/deals", keywords: "pipeline opportunities", allowed: may("deals.view") },
    { group: "Go to", label: "Quotes", href: "/quotes", keywords: "quotations", allowed: may("quotes.view") },
    { group: "Go to", label: "Activities", href: "/activities", keywords: "to do tasks calls", allowed: may("activities.view") && !field },
    { group: "Go to", label: "Calendar", href: "/calendar", keywords: "meetings schedule", allowed: may("activities.view") },
    { group: "Go to", label: "Products", href: "/products", keywords: "catalogue prices", allowed: may("products.view") },
    { group: "Go to", label: "Retention", href: "/retention", keywords: "kept lost at risk", allowed: may("customers.view") },
    { group: "Go to", label: terms.visited.many, href: "/field/doctors", keywords: "doctors field plan zones", allowed: may("visits.view") },
    { group: "Go to", label: "Visits", href: "/visits", keywords: "field", allowed: may("visits.view") },
    { group: "Go to", label: "Your profile", href: "/account", keywords: "account password performance", allowed: true },
    { group: "Create", label: "Add customer", href: "/companies/new", keywords: "new company", allowed: may("customers.create") },
    { group: "Create", label: "Add contact", href: "/contacts/new", keywords: "new person", allowed: may("customers.create") },
    { group: "Create", label: "New deal", href: "/deals/new", keywords: "opportunity", allowed: may("deals.create") },
    { group: "Create", label: "Log activity", href: "/activities/new", keywords: "call meeting note task", allowed: may("activities.create") && !field },
    { group: "Create", label: "Log visit", href: "/visits/new", keywords: "field doctor", allowed: may("visits.create") },
  ];
  return all.filter((a) => a.allowed).map(({ allowed: _, ...a }) => a);
}

export default async function Layout({ children }: { children: ReactNode }) {
  // Who you are and what isn't set up yet (a product with no price, in red):
  // one request, shared with the page below (lib/api.ts getFrame).
  const { me, unset: counts } = await getFrame();
  const unset = counts ?? undefined;
  // The bell's notifications are the attention prompts; not awaited, so no page waits for them.
  const notifications = load<Prompt[]>("/attention").catch(() => [] as Prompt[]);
  return (
    <ShellLayout unset={unset} notifications={notifications} allHref="/attention" search={me.org ? <CommandMenuButton /> : undefined}>
      <TermsProvider terms={termsOf(me)}>
        <CanProvider permissions={me.permissions ?? []}>{children}</CanProvider>
      </TermsProvider>
      {isFieldAgent(me) && me.org && <FieldTracker userId={me.user.id} timeZone={me.org.timezone} />}
      {me.org && <CommandMenu actions={menuActions(me)} />}
    </ShellLayout>
  );
}
