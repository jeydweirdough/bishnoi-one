"use client";

import type { ReactNode } from "react";
import { Sidebar, type Process, type Step } from "@/src/platform/shell/sidebar";
import type { MyModule } from "@/src/one/module-switcher";
import { Icon, type IconName } from "@/src/platform/ui/icons";
import { peoplePagesFor, settingsPagesFor } from "@/src/modules/crm/lib/access";
import type { Me } from "@/src/platform/lib/types";

// The CRM's menu as Zoho CRM lays it out (decided 2026-10-24, benchmarks/surpass.md §1): Sales
// (leads to retention, in order), Activities, Field sales, Products, Documents, in Zoho's names and standard
// words (no company Terms); users and roles and settings at the foot. The sidebar itself is src/platform/shell/sidebar.tsx.
//
// A division is a property of a record, not a place, so these are the same pages whichever
// division someone sells in. The Administrator sees every area the roles under them see, and more
// (decided 2026-10-26: "im the admin, im much higher"); only a field agent sees less than their
// permissions reach, on purpose: their customers are their doctors.

/** How many things wait on this person, by kind (none are counted in the CRM today). */
export type Waiting = Record<string, number>;

/** How many things aren't set up yet, by kind (the API's /unset). */
export type Unset = Record<string, number>;

function menu(me: Me, unset: Unset): { home: Step; processes: Process[]; foot: Process[] } {
  const may = (permission: string) => me.permissions?.includes(permission) ?? false;
  const admin = me.isOwner;
  const agent = may("visits.create") && !may("quotes.view") && !may("goals.view");
  // Everyone who isn't a field agent works the customer side, the Administrator included.
  const selling = !agent;
  const when = (show: boolean, step: Step): Step[] => (show ? [step] : []);
  const priced = unset.productPrices ?? 0;

  // As Zoho CRM groups it: Sales, Activities, Field sales, Products, Documents.
  // The sales hierarchy, in the order a customer moves through it: a lead becomes a customer (with its
  // contacts), a deal is worked, quoted, ordered, then the customer is kept.
  const sales: Process = {
    label: "Sales",
    icon: "deals",
    flow: true,
    steps: [
      ...when(may("customers.inbox"), { href: "/crm/inbox", label: "Leads", icon: "inbox" }),
      ...when(selling && may("customers.view"), { href: "/crm/customers", label: "Customers", icon: "customers", also: ["/crm/customers"] }),
      ...when(selling && may("customers.view"), { href: "/crm/contacts", label: "Contacts", icon: "person" }),
      ...when(selling && may("deals.view"), { href: "/crm/deals", label: "Deals", icon: "deals" }),
      ...when(selling && may("quotes.view"), { href: "/crm/quotes", label: "Quotes", icon: "quotes" }),
      ...when(selling && may("quotes.view"), { href: "/crm/order-links", label: "Order links", icon: "orders" }),
      ...when(selling && may("customers.view"), { href: "/crm/retention", label: "Retention", icon: "retention" }),
    ],
  };
  const work: Process = {
    label: "Activities",
    icon: "calendar",
    steps: [
      ...when(may("activities.view"), { href: "/crm/calendar", label: "Calendar", icon: "calendar" }),
      // A field agent's calls are their visits: one log, not two.
      ...when(!agent && may("activities.view"), { href: "/crm/activities", label: "Activities", icon: "activity", also: ["/crm/follow-ups"] }),
      ...when(!agent && may("activities.create"), { href: "/crm/email", label: "Emails", icon: "email" }),
    ],
  };
  // A field agent's week: their accounts, planned, visited, on the road; patients helped.
  const field: Process = {
    label: "Field sales",
    icon: "visit",
    steps: [
      ...when(may("goals.view"), { href: "/crm/field", label: "Team progress", icon: "goals", exact: true, also: ["/crm/field/goals", "/crm/field/balances"] }),
      ...when(may("visits.view"), { href: "/crm/field/doctors", label: "Accounts to visit", icon: "customers", also: agent ? ["/crm/customers", "/crm/contacts"] : [] }),
      ...when(may("goals.view") || agent, { href: "/crm/field/routes", label: agent ? "My route" : "Routes", icon: "trend" }),
      ...when(may("visits.view"), { href: "/crm/visits", label: "Visits", icon: "visit" }),
      ...when(may("visits.view"), { href: "/crm/field/assistance", label: "Patient assistance", icon: "approvals" }),
    ],
  };
  const catalogue: Process = {
    label: "Products",
    icon: "products",
    steps: [
      ...when(may("products.view"), { href: "/crm/products", label: "Products", icon: "products", missing: priced ? { count: priced, says: `${priced} ${priced === 1 ? "product has" : "products have"} no price at every price type` } : undefined }),
      ...when(may("products.prices"), { href: "/crm/prices", label: "Price books", icon: "pricing" }),
      ...when(may("products.view"), { href: "/crm/promos", label: "Promotions", icon: "promos" }),
      ...when(may("products.view"), { href: "/crm/bundles", label: "Bundles", icon: "bundles" }),
    ],
  };
  const documents: Process = {
    label: "Documents",
    icon: "letters",
    steps: [
      ...when(may("customers.view") || may("admin.settings"), { href: "/crm/media", label: "Documents", icon: "letters" }),
      ...when(may("department.manage") || may("admin.settings"), { href: "/crm/materials", label: "Promotional materials", icon: "approvals" }),
    ],
  };
  // Reports: one row (decided 2026-10-26). The Reports Center lists its own categories, each only
  // for a role that may see its data (the API's app/routers/reports.py checks the same).
  const reports: Process = {
    label: "Reports",
    icon: "reports",
    steps: [
      { href: "/crm/reports", label: "Reports", icon: "reports", exact: true, also: ["/crm/reports"] },
    ],
  };
  // A field agent's day comes first; everyone else's starts with sales.
  const processes = agent ? [field, work, catalogue, documents, reports] : [sales, work, field, catalogue, documents, reports];

  const people = peoplePagesFor(me);
  const fullSettings = may("admin.settings") || may("admin.types");
  const canSettings = fullSettings || may("department.manage");
  const settingsSteps: Step[] = canSettings
    ? [
        {
          href: "/crm/admin/settings/company",
          label: "General",
          icon: "company",
          also: ["/crm/admin/settings/company", "/crm/admin/settings/quote-templates", "/crm/admin/settings/emails", "/crm/admin/settings/terms"],
        },
        {
          href: "/crm/admin/settings",
          label: "Customization",
          icon: "settings",
          also: ["/crm/admin/settings", "/crm/admin/settings/customer-types", "/crm/admin/settings/deal-stages", "/crm/admin/settings/associations"],
        },
        {
          href: "/crm/admin/settings/pricing",
          label: "Sales & Pricing",
          icon: "pricing",
          also: ["/crm/admin/settings/pricing", "/crm/admin/settings/price-rules", "/crm/admin/settings/performance", "/crm/admin/settings/retention-windows", "/crm/admin/settings/attention", "/crm/admin/settings/kpis"],
        },
        {
          href: "/crm/admin/settings/connections",
          label: "Connections",
          icon: "apps",
          also: ["/crm/admin/settings/connections"],
        },
      ]
    : [];

  const foot: Process[] = [
    { label: "Users and roles", icon: "people", steps: people.map((p) => ({ href: p.href, label: p.label === "Roles and permissions" ? "Roles" : p.label, icon: p.href.includes("roles") ? "roles" : p.href.includes("teams") ? "teams" : "people" })) },
    {
      label: fullSettings ? "Settings" : "Department settings",
      section: "Administration",
      icon: "settings",
      steps: [
        ...settingsSteps,
        ...when(may("admin.audit"), { href: "/crm/admin/audit", label: "Activity log", icon: "auditLog" }),
      ],
    },
  ];
  const home: Step = admin ? { href: "/crm", label: "Dashboard", icon: "overview", exact: true } : { href: "/crm", label: "Home", icon: "home", exact: true };
  return { home, processes, foot };
}

export function Nav({ me, mine = [], unset = {}, rail = false, actions }: { me: Me; mine?: MyModule[]; waiting?: Waiting; unset?: Unset; rail?: boolean; actions?: ReactNode }) {
  const { home, processes, foot } = menu(me, unset);
  return (
    <Sidebar
      module="crm"
      company={me.org?.brandName ?? me.org?.name}
      mine={mine}
      home={home}
      processes={processes}
      foot={foot}
      icon={(name, className) => <Icon name={name as IconName} className={className} />}
      rail={rail}
      actions={actions}
    />
  );
}
