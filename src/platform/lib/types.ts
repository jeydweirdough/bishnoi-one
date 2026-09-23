// Shapes returned by the API (api/app/routers). camelCase on the wire.

// "prices" is setting what one team charges: its own amounts over the company's
// price list, and which price types it quotes with. A team lead's, not a rep's.
export type Action = "view" | "create" | "edit" | "delete" | "report" | "prices";

// Settings is not one switch. `manage` runs the company, every screen of it;
// `recover` is the narrower key a Developer Admin holds, for the screens you
// need when something is broken.
export type SettingsAction = "manage" | "recover";

// The steps of an order, taken in the Orders app; Orbit holds who may take which.
export type OrderAction =
  | "view"
  | "raise"
  | "edit"
  | "endorse"
  | "approve"
  | "send_back"
  | "reject"
  | "verify_payment"
  | "hold"
  | "fulfil"
  | "deliver"
  | "delete"
  | "restore";

export type TeamAccess = { code: string; name: string; actions: Action[] };

export type ModuleAccess = {
  key: string;
  name: string;
  // "app": its screens are another app's (Orders); `url` is where, once it's live.
  kind: "sales" | "department" | "app";
  built: boolean;
  url?: string | null;
  actions: Action[];
  teams: TeamAccess[];
};

export type Org = {
  id: string;
  slug: string;
  name: string;
  brandName: string;
  currency: string;
  locale: string;
  timezone: string;
  /** Decimal places the currency keeps: two for pesos, none for yen. Two when the API doesn't say. */
  minorUnits?: number;
};

/** One company as the switcher lists it. `isMine` is false for a company a
 *  Developer Admin can open but does not work in. */
export type CompanyListing = Org & { status: string; isMine: boolean };

/** Every company this person can open. `everyCompany` is true for a Developer
 *  Admin, for whom that is the whole platform. `current` is null on the
 *  platform, where no company is open yet. */
export type Companies = { current: string | null; everyCompany: boolean; items: CompanyListing[] };

/** One company as the platform lists it: what it is, and whether anybody can
 *  yet sign in to it. */
export type PlatformCompany = Org & {
  status: string;
  orderPrefix: string;
  template: string;
  createdAt: string;
  peopleCount: number;
  /** True once it has somebody who can run it. */
  isReady: boolean;
};

/** One person in a company, as the platform lists them. */
export type CompanyPerson = {
  id: string;
  email: string;
  fullName: string;
  isAdmin: boolean;
  isOwner: boolean;
  moduleCount: number;
  isDeveloperAdmin: boolean;
};

/** What a company needs to join the platform, and the person who will run it. */
export type NewCompanyInput = {
  name: string;
  slug?: string | null;
  brandName?: string | null;
  currency: string;
  timezone: string;
  orderPrefix?: string | null;
  adminEmail: string;
  adminName: string;
  adminPassword: string;
};

/** One choice on a company's own pick-list. `icon` is a name from the icon registry, where the list has icons. */
export type ListItem = { code: string; name: string; icon: string | null; isActive: boolean };

/** The pick-lists a company writes for itself. Everything else here is Orbit's own vocabulary. */
export type ListKind = "customer_kind" | "activity_kind" | "outcome";
export type CompanyLists = Record<ListKind, ListItem[]>;

export type Me = {
  // `photoAt`: when their picture last changed, or null when they have none (initials are drawn instead).
  user: { id: string; email: string; fullName: string; photoAt: string | null };
  // The company this session works in, and null for a Developer Admin who has
  // not opened one: they sign in to the platform, which is in no company.
  // Everything else here is within whichever company that is.
  org: Org | null;
  canManageSettings: boolean;
  // Holds the recovery key itself (a Developer Admin). Not "can reach the
  // recovery screens" -- each screen's rule combines this with the two below.
  canRecover: boolean;
  // Set when a Developer Admin is looking through this person's eyes. The
  // screens resolve as the person; this says who is really at the keyboard,
  // and every change is refused while it is set.
  viewedBy: { email: string; fullName: string } | null;
  // Owns the company, so decides what it is. Admins cannot grant this to
  // themselves; it is set on the membership, never through a role.
  isOwner: boolean;
  /** The tier above every company. Never a role, so no company's admins can
   *  grant it; it is set on the platform (api app/platform.py). */
  isDeveloperAdmin: boolean;
  modules: ModuleAccess[];
  // The company's own words for its customers, its activities and how a call went.
  // Only the switched-on ones: a record holding a switched-off code falls back to the code.
  lists: CompanyLists;
};

// A company writes these lists itself, so the app only ever knows them as codes.
export type CustomerKind = string;
export type CustomerStatus = "lead" | "active" | "inactive";
export type ActivityKind = string;
export type Outcome = string;
export type Bucket = "overdue" | "today" | "upcoming";

/** Settings → Lists: every list a company can edit, switched-off items and all. */
export type ListSettings = {
  kinds: { kind: ListKind; label: string; hint: string; hasIcons: boolean; required: boolean }[];
  lists: CompanyLists;
};

export type Person = { id: string | null; name: string | null };

export type Customer = {
  id: string;
  rev: string | null;
  /** Which division this record is in. The sales workspace spans every
   *  division a person sells in, so a record has to say. */
  division: string;
  divisionName: string;
  team: string;
  teamName: string;
  headquarters: string | null;
  headquartersName: string | null;
  name: string;
  kind: CustomerKind;
  status: CustomerStatus;
  specialty: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  city: string | null;
  notes: string | null;
  owner: Person;
  lastContactAt: string | null;
  createdAt: string | null;
  updatedAt: string | null;
  can: { edit: boolean; delete: boolean; log: boolean };
};

export type Activity = {
  id: string;
  customerId: string;
  customerName: string | null;
  /** Which division this record is in. The sales workspace spans every
   *  division a person sells in, so a record has to say. */
  division: string;
  divisionName: string;
  team: string;
  teamName: string;
  kind: ActivityKind;
  outcome: Outcome | null;
  summary: string;
  occurredAt: string;
  by: Person;
  can: { delete: boolean };
};

export type FollowUp = {
  id: string;
  rev: string | null;
  customerId: string;
  customerName: string | null;
  /** Which division this record is in. The sales workspace spans every
   *  division a person sells in, so a record has to say. */
  division: string;
  divisionName: string;
  team: string;
  teamName: string;
  title: string;
  dueOn: string;
  bucket: Bucket | null;
  status: "open" | "done";
  assignee: Person;
  doneAt: string | null;
  doneBy: Person | null;
  can: { edit: boolean };
};

export type CustomerDetail = Customer & { activities: Activity[]; followUps: FollowUp[]; quotes: Quote[] };

export type CustomerList = { items: Customer[]; total: number };

export type Summary = {
  today: string;
  counts: { customers: number; leads: number; overdue: number; dueToday: number; upcoming: number };
  dueFollowUps: FollowUp[];
  recentActivity: Activity[];
};

export type HomeFollowUp = {
  id: string;
  module: string;
  moduleName: string;
  team: string;
  teamName: string;
  customerId: string;
  customerName: string | null;
  title: string;
  dueOn: string;
  bucket: Bucket;
};

export type Duplicate = { id: string; name: string; teamName: string | null; phone: string | null };

export type Headquarters = { code: string; name: string; isActive: boolean };
export type OrgTeam = { code: string; name: string; isActive: boolean; headquarters: Headquarters[] };
export type OrgDivision = {
  code: string;
  name: string;
  kind: "sales" | "department" | null;
  /** Built-in divisions come with Orbit's modules: they have screens and can't be switched off. */
  isBuiltIn: boolean;
  /** An icon name an Admin picked; null leaves the built-in one. */
  icon: string | null;
  isActive: boolean;
  spansDivisions: boolean;
  teams: OrgTeam[];
};

// --- settings ---

export type AdminAssignment = {
  id: string;
  roleKey: string;
  roleName: string;
  moduleKey: string;
  moduleName: string;
  divisionCode: string | null;
  subdivisionCode: string | null;
  scopeLabel: string;
};

export type AdminUser = {
  id: string;
  email: string;
  fullName: string;
  photoAt: string | null;
  isActive: boolean;
  createdAt: string;
  assignments: AdminAssignment[];
};

export type Role = { key: string; name: string; description: string; assignmentCount: number };

export type RolesPayload = {
  roles: Role[];
  // `reaches`: the divisions an app module (Orders) may be assigned in; null for the rest.
  modules: { key: string; name: string; kind: "sales" | "department" | "app"; built: boolean; actions: string[]; reaches: string[] | null }[];
  actions: Action[];
  // The Orders module's steps, grouped as the role screen shows them.
  orderSteps: { group: string; steps: { action: OrderAction; label: string }[] }[];
  // The two keys to Settings: running the company, and keeping it working.
  settingsActions: { action: SettingsAction; label: string; hint: string }[];
  // role key -> module key -> actions ("settings" -> ["manage"])
  permissions: Record<string, Record<string, string[]>>;
};

// --- pricing (money in whole centavos, percentages in basis points: 1250 = 12.5%) ---

export type PriceEntry = "list" | "entered";
export type PriceRule = "always" | "with_rx";

export type PriceType = {
  code: string;
  name: string;
  entry: PriceEntry;
  requiresNotes: boolean;
  needsApproval: boolean;
  isActive: boolean;
};

export type Issuer = { code: string; name: string; isActive: boolean };

export type DivisionPricing = {
  code: string;
  name: string;
  usesPriceList: boolean;
  allowsGuaranteeLetters: boolean;
  discountApprovalBp: number;
  priceTypes: Record<string, PriceRule>;
};

/** Another application this company reaches from Orbit. Which applications it
 *  has and where they live is a company's own setting (Settings → Apps), so
 *  adding one later needs no deployment. */
export type AppLink = {
  code: string;
  name: string;
  url: string;
  description: string;
  icon: string | null;
  /** Orbit ships with this one, so it can be renamed and moved but not removed:
   *  its permissions live in code and are granted to people. */
  isBuiltIn: boolean;
  isActive: boolean;
  /** True once it has an address. Until then it is never offered to anyone. */
  isReady: boolean;
};

export type PricingRules = {
  priceTypes: PriceType[];
  issuers: Issuer[];
  divisions: DivisionPricing[];
  /** Which way a newly added bundle starts. A default, not a rule. */
  bundlesAsOneLine: boolean;
};

// --- a team's own prices (Prices, inside a sales module) ---

/** One of the division's price types, with whether this team quotes with it. */
export type TeamPriceType = { code: string; name: string; entry: PriceEntry; rule: PriceRule; chosen: boolean };

/** What one product costs at one price type. `team` is null when the team hasn't set one: it follows the company. */
export type TeamPriceCell = { company: number | null; team: number | null };

export type TeamPricedProduct = { id: string; code: string; name: string; unit: string; prices: Record<string, TeamPriceCell> };

export type TeamPrices = {
  division: string;
  divisionName: string;
  team: string;
  teamName: string;
  /** True while the team hasn't narrowed its price types: it quotes with whatever its division does. */
  usesDivisionTypes: boolean;
  priceTypes: TeamPriceType[];
  products: TeamPricedProduct[];
};

/** One price on its way back to the API. A null amount clears it, handing that price back to the company's. */
export type TeamPriceInput = { productId: string; priceTypeCode: string; amountCentavos: number | null };

/** Settings → Company: the record every screen reads its money, dates and times from. */
export type Company = Org & {
  orderPrefix: string;
  /** The starting setup the company was made from. Fixed once it exists. */
  template: string;
  /** The API's own rendering of 123456 minor units, so a change can be shown before it's saved. */
  example: string;
  /** The currency codes the API can draw a symbol for; anything else prints as its code. */
  knownCurrencies: string[];
};

export type PromoKind = "percent" | "amount" | "free_goods" | "tiered";
export type PromoTier = { minQty: number; percentBp: number };

/** What a promo does; all a rep needs to pick one. */
export type PromoTerms = {
  id: string;
  name: string;
  kind: PromoKind;
  percentBp: number | null;
  amountCentavos: number | null;
  buyQty: number | null;
  freeQty: number | null;
  tiers: PromoTier[];
  productIds: string[] | null; // null: every product
};

export type Promo = PromoTerms & {
  startsOn: string;
  endsOn: string | null;
  divisionCodes: string[];
  isActive: boolean;
  state: "running" | "upcoming" | "ended" | "off";
};

export type Product = {
  id: string;
  code: string;
  name: string;
  genericName: string | null;
  strength: string | null;
  form: string | null;
  unit: string;
  isActive: boolean;
  prices: Record<string, number>;
  updatedAt: string | null;
};

export type BundleItem = { productId: string; qty: number };

/** A set of products at one price. `asOneLine` decides only what the customer
 *  reads on the quote — the total is the same either way. */
export type Bundle = {
  id: string;
  code: string;
  name: string;
  priceCentavos: number;
  asOneLine: boolean;
  items: BundleItem[];
  startsOn: string;
  endsOn: string | null;
  divisionCodes: string[];
  isActive: boolean;
  state: "running" | "upcoming" | "ended" | "off";
};

export type InventoryReference = {
  priceTypes: { code: string; name: string; isActive: boolean }[];
  divisions: { code: string; name: string }[];
};

export type InventorySummary = { counts: { products: number; missingPrices: number; runningPromos: number } };

/** What a rep in one division may quote with. */
export type PriceList = {
  usesPriceList: boolean;
  allowsGuaranteeLetters: boolean;
  discountApprovalBp: number;
  priceTypes: (Omit<PriceType, "isActive"> & { rule: PriceRule })[];
  issuers: { code: string; name: string }[];
  products: Omit<Product, "isActive" | "updatedAt">[];
  promos: PromoTerms[];
  /** Picked instead of a product, not on top of one. */
  bundles: Pick<Bundle, "id" | "code" | "name" | "priceCentavos" | "asOneLine" | "items">[];
};

export type ApprovalReason = "price" | "discount";

export type QuoteLine = {
  productId: string;
  productCode: string;
  productName: string;
  unit: string;
  quantity: number;
  freeQuantity: number;
  unitPriceCentavos: number;
  grossCentavos: number;
  promoId: string | null;
  promoName: string | null;
  promoDiscountCentavos: number;
  discountKind: "percent" | "amount" | null;
  discountValue: number | null;
  discountCentavos: number;
  totalCentavos: number;
  /** Set when the line came from a bundle. On a one-line bundle `productId` is
   *  empty and `contents` names what is in the set. */
  bundleId: string | null;
  bundleName: string | null;
  contents: string;
};

export type Payment = {
  id: string;
  paidOn: string;
  amountCentavos: number;
  reference?: string;
  byName?: string;
  at: string;
};

export type Quote = {
  id: string;
  rev: string | null;
  number: string;
  division: string;
  divisionName: string;
  team: string;
  teamName: string;
  customerId: string;
  customerName: string | null;
  priceType: string;
  priceTypeName: string;
  rx: boolean;
  payer: string;
  payerName: string | null;
  notes: string | null;
  lines: QuoteLine[];
  grossCentavos: number;
  promoDiscountCentavos: number;
  discountCentavos: number;
  totalCentavos: number;
  state: "waiting" | "ready" | "rejected";
  approval: {
    status: "none" | "pending" | "approved" | "rejected";
    reasons: ApprovalReason[];
    note: string | null;
    by: Person | null;
    at: string | null;
  };
  letter: {
    number: string;
    issuedOn: string;
    amountCentavos: number;
    file: { name: string; contentType: string; size: number } | null;
    status: "pending" | "verified" | "rejected";
    note: string | null;
    by: Person | null;
    at: string | null;
  } | null;
  payment: { status: "none" | "unpaid" | "partial" | "paid"; paidCentavos: number; payments: Payment[] };
  createdAt: string;
  createdBy: Person;
  can: { delete?: boolean; approve?: boolean; checkLetter?: boolean; recordPayment?: boolean; order?: boolean };
};

export type QuotePreview = {
  priceType: string;
  lines: Pick<
    QuoteLine,
    | "productId"
    | "quantity"
    | "freeQuantity"
    | "unitPriceCentavos"
    | "grossCentavos"
    | "promoDiscountCentavos"
    | "discountCentavos"
    | "totalCentavos"
    | "productCode"
    | "productName"
    | "bundleId"
    | "bundleName"
    | "contents"
  >[];
  grossCentavos: number;
  promoDiscountCentavos: number;
  discountCentavos: number;
  totalCentavos: number;
  approvalReasons: ApprovalReason[];
};

export type FinanceTask = "approvals" | "letters" | "payments";
export type FinanceSummary = { counts: Record<FinanceTask, number> };

// --- retention (a customer is "kept" when they get a quote that isn't rejected) ---

export type Health = "healthy" | "at_risk" | "lost" | "no_quotes";

export type RetentionSummary = {
  rate: number | null; // null: nobody to measure yet
  base: number; // quoted in the previous window
  retained: number; // ...and again in the latest one
  lost: number;
  new: number;
  customers: number;
  healthy: number;
  atRisk: number;
  lostNow: number;
  noQuotes: number;
};

export type TrendPoint = { month: string; asOf: string; rate: number | null; base: number; retained: number };

export type RetentionRules = { atRiskDays: number; lostDays: number };

export type NextFollowUp = { dueOn: string; title: string; assignee: string | null } | null;

export type WatchRow = {
  customerId: string;
  name: string;
  division: string;
  divisionName: string;
  team: string;
  teamName: string;
  owner: Person;
  health: Health;
  status: CustomerStatus;
  lastQuoteOn: string | null;
  daysSince: number;
  followUp: NextFollowUp;
  canWinBack: boolean;
};

/** A window per division: each decides for itself when a customer has gone
 *  quiet, so a merged list groups rather than averages. */
export type DivisionRules = RetentionRules & { division: string; divisionName: string };

export type ModuleRetention = {
  view: "mine" | "team";
  canSeeTeam: boolean;
  asOf: string;
  rules: DivisionRules[];
  summary: RetentionSummary;
  trend: TrendPoint[];
  reps: (RetentionSummary & { id: string | null; name: string | null })[];
  watch: WatchRow[];
};

export type AtRiskItem = {
  customerId: string;
  name: string;
  module: string;
  moduleName: string;
  teamName: string;
  lastQuoteOn: string | null;
  daysSince: number;
  lostAfterDays: number;
  followUp: NextFollowUp;
  canWinBack: boolean;
};

export type MyAtRisk = { today: string; recentlyLost: number; items: AtRiskItem[] };

export type DivisionRetention = { code: string; name: string; rules: RetentionRules; summary: RetentionSummary; trend: TrendPoint[] };

export type RetentionByDivision = {
  asOf: string;
  divisions: DivisionRetention[];
  total: { summary: RetentionSummary; trend: TrendPoint[] };
};

export type RetentionRuleRow = { code: string; name: string } & RetentionRules;

// --- focus goals and the home dashboard (units: percent in basis points, money in centavos) ---

export type GoalUnit = "percent" | "count" | "money" | "days";
export type GoalArea = "sales" | "finance" | "inventory";

export type GoalDef = {
  key: string;
  name: string;
  unit: GoalUnit;
  better: "higher" | "lower";
  area: GoalArea;
  perRepMonthly: boolean;
  about: string;
  default: number;
};

export type GoalStatus = "met" | "on_pace" | "behind" | "below" | "over" | "no_data";

export type GoalResult = { key: string; value: number | null; target: number; expected: number | null; status: GoalStatus };

export type SalesGoals = { division: string; name: string; rules: RetentionRules; goals: GoalResult[]; trend: TrendPoint[] };

export type TeamGoals = SalesGoals & { people: number; rows?: { id: string; name: string; goals: GoalResult[] }[] };

export type Dashboard = {
  today: string;
  month: { start: string; days: number; day: number };
  goals: GoalDef[];
  mine: (SalesGoals & { customers: number })[];
  teams: TeamGoals[];
  divisions: TeamGoals[];
  finance: {
    counts: Record<FinanceTask, number>;
    unpaidCentavos: number;
    oldest: { id: string; number: string; customerName: string | null; divisionName: string; task: "approval" | "letter"; ageDays: number; totalCentavos: number }[];
    goals: GoalResult[];
  } | null;
  inventory: {
    products: number;
    missingCount: number;
    missing: { id: string; name: string; code: string; missing: string[] }[];
    starting: { id: string; name: string; on: string }[];
    ending: { id: string; name: string; on: string }[];
    goals: GoalResult[];
  } | null;
  admin: { people: number; switchedOff: number; noRoleCount: number; noRole: { id: string; name: string }[]; noPrices: string[] } | null;
};

export type GoalTargets = {
  goals: GoalDef[];
  divisions: { code: string; name: string; area: GoalArea }[];
  targets: Record<string, Record<string, number>>;
};

/** A bulk action's progress (the API's job queue). Failures name each record that wasn't done and why. */
export type Job = {
  id: string;
  label: string;
  status: "queued" | "running" | "done";
  total: number;
  processed: number;
  succeeded: number;
  failed: number;
  failures: { id: string; error: string }[];
};

// --- order settings (Settings -> Orders) ---

export type OrderListKind =
  | "payment_method"
  | "payment_term"
  | "source"
  | "delivery_method"
  | "invoicing_entity"
  | "field_section";
export type OrderListItem = { code: string; name: string; isActive: boolean };
export type OrderFieldType = "text" | "textarea" | "number" | "date" | "choice";
export type OrderField = {
  key: string;
  label: string;
  type: OrderFieldType;
  required: boolean;
  options: string[];
  help: string;
  /** The code of a form section; null puts the field in the last one. */
  section: string | null;
  isActive: boolean;
};
export type OrderSettings = {
  kinds: { kind: OrderListKind; label: string; hint: string }[];
  lists: Record<OrderListKind, OrderListItem[]>;
  fields: OrderField[];
  rules: { largeOrderCentavos: number; recycleDays: number; orderPrefix: string; currency: string };
};

// --- the audit log ---

export type AuditEntry = { id: string; at: string; actor: string; action: string; target: string; fields: string[] };
export type AuditPage = { items: AuditEntry[]; more: boolean };

export type AppModule = RolesPayload["modules"][number];
