"use client";

import { useOperatorCompanies } from "@/src/platform/shell/features";
import { switchCompany } from "@/src/one/actions";
import { Check, ChevronRight, ChevronsUpDown } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import type { ModuleKey } from "@/src/platform/lib/modules";
import type { MyModule } from "@/src/one/module-switcher";
import { Breadcrumbs } from "./crumbs";
import { useOneMenu } from "@/src/one/menu/context";
import { Icon, type IconName } from "@/src/platform/ui/icons";
import { APP_NAME } from "@/src/platform/lib/labels";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/src/components/ui/collapsible";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/src/components/ui/dropdown-menu";
import {
  Sidebar as ShadSidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from "@/src/components/ui/sidebar";

// Drawn with shadcn/ui's Sidebar as Studio Admin draws its own (2026-11-19, owner: the whole UI on shadcn,
// Studio Admin as the basis): collapsible to icons, a sheet on a phone, areas opening in place (a menu to the side
// when collapsed). The frame round it is src/platform/shell/app-shell.tsx.
//
// Every module's sidebar (decided 2026-10-24, benchmarks/surpass.md §1, pattern P15), laid out
// as Bishnoi One Inventory's was (the user's pick) and named the way Zoho names things: the
// Bishnoi One and the company at the top, then
// Home and the main areas, in the order the work goes and with no headings, as Zoho lays it out,
// each opening in place to its pages. Only the area you're in stays open, so the menu stays short;
// closed, an area carries its pages' counts. An area with one page is a plain row. Each module
// builds its menu (src/modules/<module>/.../shell/nav.tsx) and hands it here: fix the sidebar
// here, a menu there.
//
// One menu by work (M4, 2026-11-18): inside the signed-in app the menu is the one built from the account
// (src/one/menu/one-menu.ts, given by app/(app)/layout.tsx), the same on every page whichever module keeps
// it, with no module switcher. A module's own menu only lends its red "not set up" marks, matched by address.

/** What isn't set up yet on a page: how many, and the sentence saying what. */
export type Missing = { count: number; says: string };

/** A page in the menu. `exact`: current only on itself, not on the pages under it. */
export type Step = { href: string; label: string; icon?: string; count?: number; missing?: Missing; also?: string[]; exact?: boolean };

/**
 * A main area and its pages. `section`: kept for the menus' own grouping; not shown.
 * `flow`: its pages are one process, listed in the order the work goes (kept for the menus; not
 * drawn as numbers).
 */
export type Process = { label: string; steps: Step[]; icon?: string; section?: string; flow?: boolean };

type Props = {
  /** The module keeping the page; none on the one app's own pages (Home, Reports). */
  module?: ModuleKey;
  company?: string | null;
  /** The modules this person was given (src/one/mine.ts), for the switcher. */
  mine: MyModule[];
  home?: Step | null;
  processes: Process[];
  /** Setup and administration, at the foot. */
  foot?: Process[];
  /** A small label over the foot, when it holds a different kind of work (the Admin Console's operations, 2026-10-29). */
  footLabel?: string;
  /** Each module draws its own icons by name. */
  icon: (name: string, className: string) => ReactNode;
  rail?: boolean;
  /** The top-right actions (bell, modules, account): beside the menu button on a phone. */
  actions?: ReactNode;
  /** Shown under the menu (Finance's version). */
  footer?: ReactNode;
};

const within = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

/** The page you're on: the most specific match; a page whose address asks for a query wins when the query matches. */
export function currentOf(steps: Step[], pathname: string, search: URLSearchParams | null): Step | undefined {
  let found: Step | undefined;
  let best = -1;
  for (const s of steps) {
    const [path, query] = s.href.split("?");
    const asks = [...new URLSearchParams(query ?? "")];
    let score = -1;
    if (asks.length > 0) {
      if (within(pathname, path) && asks.every(([k, v]) => search?.get(k) === v)) score = 3000 + s.href.length;
    } else if (s.exact ? pathname === path : within(pathname, path)) score = 1000 + path.length;
    for (const a of s.also ?? []) if (within(pathname, a)) score = Math.max(score, 1000 + a.length);
    if (score > best) [found, best] = [s, score];
  }
  return found;
}


type Icon = Props["icon"];

function Mark({ missing }: { missing?: Missing }) {
  if (!missing?.count) return null;
  return (
    <SidebarMenuBadge className="rounded-sm border border-destructive/20 bg-destructive/10 px-1.5 text-destructive" title={missing.says}>
      {missing.count}
    </SidebarMenuBadge>
  );
}

/** A page of its own in the menu: Home, or an area with one page. */
function LinkItem({ step, current, icon, iconName }: { step: Step; current: boolean; icon: Icon; iconName?: string }) {
  const name = iconName ?? step.icon;
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild tooltip={step.missing?.says || step.label} isActive={current}>
        <Link prefetch={false} href={step.href} aria-current={current ? "page" : undefined}>
          {name ? icon(name, "size-4") : null}
          <span>{step.label}</span>
        </Link>
      </SidebarMenuButton>
      <Mark missing={step.missing} />
    </SidebarMenuItem>
  );
}

/** A main area: opens in place to its pages; collapsed to icons, a menu beside it. */
function Area({ area, current, icon }: { area: Process; current: Step | undefined; icon: Icon }) {
  const { state, isMobile } = useSidebar();
  const inside = current !== undefined && area.steps.includes(current);
  const only = area.steps.length === 1 ? area.steps[0] : null;
  if (only) return <LinkItem step={only} current={only === current} icon={icon} iconName={only.icon ?? area.icon} />;
  const missing = area.steps.reduce((n, s) => n + (s.missing?.count ?? 0), 0);

  if (state === "collapsed" && !isMobile) {
    return (
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton tooltip={area.label} isActive={inside}>
              {area.icon ? icon(area.icon, "size-4") : null}
              <span>{area.label}</span>
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="start" sideOffset={12} className="w-56">
            <DropdownMenuLabel>{area.label}</DropdownMenuLabel>
            <DropdownMenuGroup>
              {area.steps.map((st) => (
                <DropdownMenuItem key={st.href} asChild>
                  <Link prefetch={false} href={st.href} aria-current={st === current ? "page" : undefined} className="flex items-center gap-2">
                    {st.icon ? icon(st.icon, "size-4") : null}
                    <span>{st.label}</span>
                  </Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    );
  }

  return (
    <Collapsible asChild defaultOpen={inside} className="group/collapsible">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton tooltip={area.label} isActive={inside}>
            {area.icon ? icon(area.icon, "size-4") : null}
            <span>{area.label}</span>
            <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        {missing > 0 && (
          <SidebarMenuBadge className="right-8 rounded-sm border border-destructive/20 bg-destructive/10 px-1.5 text-destructive group-data-[state=open]/collapsible:hidden">
            {missing}
          </SidebarMenuBadge>
        )}
        <CollapsibleContent>
          <SidebarMenuSub>
            {area.steps.map((st) => (
              <SidebarMenuSubItem key={st.href}>
                <SidebarMenuSubButton asChild isActive={st === current}>
                  <Link prefetch={false} href={st.href} title={st.missing?.says || st.label} aria-current={st === current ? "page" : undefined}>
                    {st.icon ? icon(st.icon, "size-4") : null}
                    <span>{st.label}</span>
                    {st.missing?.count ? <span className="ml-auto rounded-sm bg-destructive/10 px-1.5 text-xs font-medium text-destructive">{st.missing.count}</span> : null}
                  </Link>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  );
}

/** The top of the menu: Bishnoi One and the company; an operator switches company here (as Studio Admin's team switcher). */
function OneHeader({ company }: { company?: string | null }) {
  const companies = useOperatorCompanies();
  const many = Boolean(companies && companies.length > 1);
  const body = (
    <>
      <div className="flex aspect-square size-8 items-center justify-center overflow-hidden rounded-lg">
        <img src="/brand/bishnoi-one-mark.png" alt="" width={32} height={32} className="size-8" />
      </div>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-semibold">{APP_NAME}</span>
        {company && <span className="truncate text-xs text-muted-foreground">{company}</span>}
      </div>
    </>
  );
  if (!many) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton size="lg" asChild>
            <Link prefetch={false} href="/">
              {body}
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground" title="Switch company">
              {body}
              <ChevronsUpDown className="ml-auto" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg" align="start" side="bottom" sideOffset={4}>
            <DropdownMenuLabel className="text-xs text-muted-foreground">Company</DropdownMenuLabel>
            {companies!.map((c) =>
              c.current ? (
                <DropdownMenuItem key={c.slug} className="gap-2" aria-current="true">
                  <span className="min-w-0 flex-1 truncate">{c.name}</span>
                  <Check className="size-4" />
                </DropdownMenuItem>
              ) : (
                <form key={c.slug} action={switchCompany}>
                  <input suppressHydrationWarning type="hidden" name="company" value={c.slug} />
                  <DropdownMenuItem asChild>
                    <button suppressHydrationWarning type="submit" className="w-full text-left">
                      <span className="min-w-0 flex-1 truncate">{c.name}</span>
                    </button>
                  </DropdownMenuItem>
                </form>
              ),
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

/** The one menu in place of a module's own, keeping that module's red "not set up" marks by address. */
function withOneMenu(props: Props, one: ReturnType<typeof useOneMenu>): Props {
  if (!one) return props;
  const marks = new Map<string, Missing>();
  for (const st of [...props.processes, ...(props.foot ?? [])].flatMap((p) => p.steps)) if (st.missing?.count) marks.set(st.href, st.missing);
  const lend = (p: { label: string; icon: string; steps: Step[] }): Process => ({ ...p, steps: p.steps.map((st) => (marks.has(st.href) ? { ...st, missing: marks.get(st.href) } : st)) });
  return {
    ...props,
    home: one.home,
    processes: one.processes.map(lend),
    foot: one.foot.map(lend),
    footLabel: one.foot.length > 0 ? "Administration" : undefined,
    icon: (name, className) => <Icon name={name as IconName} className={className} />,
  };
}

function SidebarBody(given: Props) {
  const one = useOneMenu();
  const props = withOneMenu(given, one);
  const pathname = usePathname();
  const search = useSearchParams();
  const all = [...(props.home ? [props.home] : []), ...props.processes.flatMap((p) => p.steps), ...(props.foot ?? []).flatMap((p) => p.steps)];
  const current = currentOf(all, pathname, search);
  const group = [...props.processes, ...(props.foot ?? [])].find((p) => current && p.steps.includes(current));
  const companies = useOperatorCompanies();
  const areas = props.processes.filter((a) => a.steps.length > 0);
  const below = (props.foot ?? []).filter((a) => a.steps.length > 0);

  return (
    <>
      {/* Company / Area / Page at the top of the page, into the frame's slot. */}
      <Breadcrumbs module={one ? undefined : props.module} company={props.company} companies={companies} mine={props.mine} area={group} page={current} home={props.home} />
      <ShadSidebar variant="sidebar" collapsible="icon" className="print:hidden">
        <SidebarHeader>
          <OneHeader company={props.company} />
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {props.home && <LinkItem step={props.home} current={props.home === current} icon={props.icon} />}
                {areas.map((a) => (
                  <Area key={a.label} area={a} current={current} icon={props.icon} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
          {below.length > 0 && (
            <SidebarGroup>
              {props.footLabel && <SidebarGroupLabel>{props.footLabel}</SidebarGroupLabel>}
              <SidebarGroupContent>
                <SidebarMenu>
                  {below.map((a) => (
                    <Area key={a.label} area={a} current={current} icon={props.icon} />
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}
        </SidebarContent>
        {props.footer && <SidebarFooter className="group-data-[collapsible=icon]:hidden">{props.footer}</SidebarFooter>}
        <SidebarRail />
      </ShadSidebar>
    </>
  );
}

/** One module's sidebar: see the comment at the top. Sits inside the frame's SidebarProvider (app-shell.tsx). */
export function Sidebar(props: Props) {
  // The query decides the current step on a few pages (Inventory's filtered lists); reading it needs a boundary.
  return (
    <Suspense fallback={null}>
      <SidebarBody {...props} />
    </Suspense>
  );
}
