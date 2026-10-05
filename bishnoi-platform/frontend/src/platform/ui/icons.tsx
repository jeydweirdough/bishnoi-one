import {
  Boxes,
  HeartPulse,
  LifeBuoy,
  Megaphone,
  Siren,
  Activity,
  ArrowUpRight,
  BadgePercent,
  Building,
  Briefcase,
  Building2,
  CalendarClock,
  CalendarDays,
  ChartLine,
  CircleUserRound,
  ClipboardCheck,
  Coins,
  ContactRound,
  FileBadge,
  FileSignature,
  Gavel,
  Globe,
  HandCoins,
  History as HistoryGlyph,
  Hourglass,
  House,
  IdCard,
  Inbox,
  KeyRound,
  Landmark,
  LayoutDashboard,
  LayoutGrid,
  ListChecks,
  MapPin,
  MapPinHouse,
  MessageSquare,
  Network,
  NotebookPen,
  Package,
  Phone,
  PhoneCall,
  ReceiptText,
  Repeat,
  Scale,
  ScrollText,
  Settings,
  ShoppingCart,
  ShieldCheck,
  StickyNote,
  Tags,
  Target,
  Truck,
  UserCog,
  UserPlus,
  Users,
  UsersRound,
  Mail,
  SquareCheckBig,
  type LucideIcon,
} from "lucide-react";

// Every icon in the app, by what it means. One library (Lucide) at one stroke,
// so the same thing always wears the same picture: a page's tab, its sidebar
// link and its section heading agree. Pick by meaning, never by looks.
export const ICONS = {
  // places
  home: House,
  salesDivision: Briefcase, // every sales division: the name says which one
  reports: ChartLine,
  finance: Landmark,
  inventory: Package,
  bid: Gavel,
  hr: UsersRound,
  regulatory: Scale,
  inlicensing: FileSignature,
  dispatch: Truck,
  exec: Building2,
  orders: ShoppingCart,
  external: ArrowUpRight, // opens another app, in a new tab

  // settings
  settings: Settings,
  people: Users,
  roles: ShieldCheck,
  teams: Network,
  pricing: Tags,
  money: Coins, // how the company writes money, dates and times
  lists: ListChecks, // the company's own words for its records
  retention: Repeat,
  goals: Target,
  company: Building,
  apps: LayoutGrid, // the other applications this company reaches from Bishnoi One
  companies: Globe, // every company on the platform, for a Developer Admin
  headquarters: MapPinHouse, // a team's office: a place with a building
  auditLog: ScrollText,
  // the platform console's own places
  monitoring: HeartPulse, // whether the applications are up, and the traffic
  incidents: Siren, // something broken for many, now
  support: LifeBuoy, // complaints, bugs, requests: one person's report
  communications: Megaphone, // what the platform tells people

  // a module's sections
  overview: LayoutDashboard,
  customers: ContactRound,
  followUps: CalendarClock,
  approvals: ClipboardCheck,
  letters: FileBadge,
  payments: HandCoins,
  products: Package,
  promos: BadgePercent,
  bundles: Boxes,

  // what a sheet is about
  particulars: IdCard,
  quotes: ReceiptText,
  history: HistoryGlyph,
  logActivity: NotebookPen,
  calendar: CalendarDays,
  activity: Activity,
  trend: ChartLine,
  reps: UsersRound,
  worthACall: PhoneCall,
  goingQuiet: Hourglass,
  inbox: Inbox,
  divisions: Building2,
  profile: IdCard,
  password: KeyRound,
  account: UserCog,
  addRole: UserPlus,
  person: CircleUserRound,

  // kinds of activity
  call: Phone,
  visit: MapPin,
  message: MessageSquare,
  note: StickyNote,
  email: Mail,
  task: SquareCheckBig,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

/** An icon beside text: decorative to screen readers (the text says it), 16px unless told. */
export function Icon({ name, className = "size-4" }: { name: IconName; className?: string }) {
  const Glyph = ICONS[name];
  return <Glyph aria-hidden strokeWidth={1.75} className={`shrink-0 ${className}`} />;
}

const MODULE_ICONS: Record<string, IconName> = {
  finance: "finance",
  inventory: "inventory",
  bid: "bid",
  hr: "hr",
  regulatory: "regulatory",
  inlicensing: "inlicensing",
  dispatch: "dispatch",
  exec: "exec",
  orders: "orders",
};

/** A module's icon: departments each have their own; every sales division shares one. */
export function moduleIcon(key: string): IconName {
  return MODULE_ICONS[key] ?? "salesDivision";
}

/** A name that came from the API, only if this registry really has it. */
export function knownIcon(name: string | null | undefined): IconName | null {
  return name && name in ICONS ? (name as IconName) : null;
}

/**
 * The picture for a choice on one of the company's own lists. It wears the icon
 * its admins picked; failing that, its code where the code happens to name one;
 * failing that, a neutral glyph, so a list we've never seen still draws.
 */
export function listIcon(item: { code?: string | null; icon: string | null } | undefined, fallback: IconName = "activity"): IconName {
  return knownIcon(item?.icon) ?? knownIcon(item?.code) ?? fallback;
}

/** What an Admin can choose from when adding a department of their own. */
export const DEPARTMENT_ICONS: readonly { name: IconName; label: string }[] = [
  { name: "divisions", label: "Building" },
  { name: "people", label: "People" },
  { name: "customers", label: "Contacts" },
  { name: "trend", label: "Chart" },
  { name: "finance", label: "Bank" },
  { name: "inventory", label: "Box" },
  { name: "dispatch", label: "Truck" },
  { name: "regulatory", label: "Scales" },
  { name: "inlicensing", label: "Document" },
  { name: "bid", label: "Gavel" },
  { name: "goals", label: "Target" },
  { name: "calendar", label: "Calendar" },
];

/** What an Admin can put beside a way of dealing with a customer: a call, a visit, a chat over coffee. */
export const ACTIVITY_ICONS: readonly { name: IconName; label: string }[] = [
  { name: "call", label: "Phone" },
  { name: "worthACall", label: "Phone call" },
  { name: "visit", label: "Place" },
  { name: "message", label: "Message" },
  { name: "note", label: "Note" },
  { name: "logActivity", label: "Notebook" },
  { name: "calendar", label: "Calendar" },
  { name: "followUps", label: "Reminder" },
  { name: "person", label: "Person" },
  { name: "people", label: "People" },
  { name: "quotes", label: "Receipt" },
  { name: "activity", label: "Activity" },
];
