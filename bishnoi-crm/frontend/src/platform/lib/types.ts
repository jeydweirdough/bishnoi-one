// Shapes returned by the API (api/app/routers). camelCase on the wire.

// "prices" is setting what one team charges: its own amounts over the company's
// price list, and which price types it quotes with. A team lead's, not a rep's.
export type Action = "view" | "create" | "edit" | "delete" | "report" | "prices";

// Settings is not one switch. `manage` runs the company, every screen of it;
// `recover` is the narrower key a Developer Admin holds, for the screens you
// need when something is broken.
export type SettingsAction = "manage" | "recover";

// The steps of an order, taken in the Orders app; Bishnoi One holds who may take which.
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
  kind: "crm" | "department" | "app";
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
  /** The company's own words (Settings → Terms; src/components/terms). */
  terms?: {
    visited: { one: string; many: string };
    visitedType: string | null;
    detailing: string;
    site: string;
    genericName: string;
  };
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

/** The pick-lists a company writes for itself. Everything else here is Bishnoi One's own vocabulary. */
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
  /** Bishnoi One Order is connected, so ready quotes can be raised as orders. */
  ordersLinked?: boolean;
  /** Bishnoi One Pharmacy is connected, so Rx quotes can be sent for the pharmacist's check. */
  pharmacyLinked?: boolean;
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
  /** The CRM's own access (its Administration): the person's role, team, and
   *  every permission the role gives, as "area.action". */
  role?: { id: string; name: string; scope: Scope };
  team?: { id: string; name: string } | null;
  permissions?: string[];
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

export type Duplicate = { id: string; name: string; teamName: string | null; phone: string | null; canOpen?: boolean };

export type Headquarters = { code: string; name: string; isActive: boolean };
export type OrgTeam = { code: string; name: string; isActive: boolean; headquarters: Headquarters[] };
export type OrgDivision = {
  code: string;
  name: string;
  kind: "sales" | "department" | null;
  /** Built-in divisions come with Bishnoi One's modules: they have screens and can't be switched off. */
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
  modules: { key: string; name: string; kind: "crm" | "department" | "app"; built: boolean; actions: string[]; reaches: string[] | null }[];
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

/** Another application this company reaches from Bishnoi One. Which applications it
 *  has and where they live is a company's own setting (Settings → Apps), so
 *  adding one later needs no deployment. */
export type AppLink = {
  code: string;
  name: string;
  url: string;
  description: string;
  icon: string | null;
  /** Bishnoi One ships with this one, so it can be renamed and moved but not removed:
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
  /** The team's id. */
  team: string;
  teamName: string;
  /** True while the team hasn't narrowed its price types: it quotes with every one there is. */
  usesAllTypes: boolean;
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
  /** Its last day (YYYY-MM-DD), for the tag's "3 days left". null: no end set. */
  endsOn: string | null;
};

export type Promo = PromoTerms & {
  startsOn: string;
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
  /** For VAT, as Finance's tax pack names it (the price rules' tax step). */
  vatCategory?: "standard" | "zero_rated" | "exempt";
  /** Rx: sold only on a prescription. */
  needsPrescription?: boolean;
  isActive: boolean;
  /** Its code, name, unit, state and SRP are Bishnoi One Inventory's, changed there. */
  fromInventory?: boolean;
  prices: Record<string, number>;
  extra: ExtraValues;
  updatedAt: string | null;
};

/** The link to Bishnoi One Inventory, where the product list comes from when it's set up. */
export type InventoryLink = { linked: boolean; syncedAt: string | null; error: string | null; appUrl: string | null };

/** How much Inventory has of a product: out, low, ok, over (null for a service). */
export type StockLevel = {
  sku: string;
  state: "out" | "low" | "ok" | "over" | null;
  available: number;
  onHand: number;
  inTransit: number;
  warehouses: { id: string; code: string; name: string; available: number; onHand: number; inTransit: number }[];
};

/** Stock by product code; null for a product Inventory doesn't have. `error`: Inventory couldn't be asked. */
export type StockAnswer = { linked: boolean; items: Record<string, StockLevel | null>; error: string | null };

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
  bundles: Pick<Bundle, "id" | "code" | "name" | "priceCentavos" | "asOneLine" | "items" | "endsOn">[];
};

export type ApprovalReason = "price" | "discount" | "asked" | "margin" | "s2_license";

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
  /** From the price rules (Settings → Price rules). */
  volumeDiscountCentavos?: number;
  volumeName?: string | null;
  surchargeCentavos?: number;
  surchargeName?: string | null;
  /** Where the price came from: group_price, team_price, list_price, entered. */
  priceSource?: string | null;
  /** Finance's tax on the line, when the price rules add tax. */
  taxCentavos?: number;
  totalCentavos: number;
  /** Set when the line came from a bundle. On a one-line bundle `productId` is
   *  empty and `contents` names what is in the set. */
  bundleId: string | null;
  bundleName: string | null;
  contents: string;
};

/** Finance's tax on a quote, as the invoice will show it. */
export type QuoteTax = {
  document: string;
  regime: string;
  regimeName: string;
  pricesIncludeTax: boolean;
  summary: { key: string; label: string; amountCentavos: number }[];
  notice: string | null;
  totalDueCentavos: number;
  on: string;
};

export type Payment = {
  id: string;
  paidOn: string;
  amountCentavos: number;
  reference?: string;
  byName?: string;
  at: string;
};

export type QuoteOrder = { id: string; number: string; url: string | null; status: string | null; by: { id: string; name: string }; at: string };

export type Quote = {
  id: string;
  rev: string | null;
  number: string;
  /** The deal it was made for (CRM). */
  deal?: { id: string; name: string } | null;
  team: string;
  teamName: string;
  /** Who it's for: a company, or a contact (and the company they're in). */
  company: Ref | null;
  contact: Ref | null;
  customerId: string;
  customerHref: string | null;
  customerName: string | null;
  priceType: string;
  priceTypeName: string;
  rx: boolean;
  /** Attached by the customer on an order link, for Rx medicines: opened at /quotes/{id}/prescriptions/{n}. */
  prescriptions?: { n: number; name: string; contentType: string; size: number }[];
  /** Other documents the order link asked for (a valid ID...): opened at /quotes/{id}/documents/{n}. */
  documents?: { n: number; label: string | null; name: string; contentType: string; size: number }[];
  payer: string;
  payerName: string | null;
  notes: string | null;
  lines: QuoteLine[];
  grossCentavos: number;
  promoDiscountCentavos: number;
  discountCentavos: number;
  totalCentavos: number;
  /** None: priced without the tax step. */
  tax?: QuoteTax | null;
  state: "waiting" | "ready" | "rejected";
  approval: {
    status: "none" | "pending" | "approved" | "rejected";
    reasons: ApprovalReason[];
    note: string | null;
    by: Person | null;
    at: string | null;
    /** Who it waits on, while pending: the team's approvers, else its manager, else whoever reaches every team. */
    approvers: { id: string; name: string; role: string; isMe?: boolean }[];
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
  /** From the quote settings when it was made. */
  validUntil: string | null;
  terms: string | null;
  extra: ExtraValues;
  createdAt: string;
  createdBy: Person;
  owner: Person | null;
  can: { delete?: boolean; approve?: boolean; checkLetter?: boolean; recordPayment?: boolean; order?: boolean; sendToPharmacy?: boolean };
  /** The pharmacist's check in Bishnoi One Pharmacy; null when the quote isn't Rx. */
  pharmacy?: PharmacyCheck | null;
  /** The order raised from it in Bishnoi One Order; null until then. */
  order?: QuoteOrder | null;
};

export type PharmacyOutcome = "not_sent" | "waiting" | "verified" | "needs_clarification" | "rejected";

export type PrescriptionDetails = {
  prescriberName: string;
  prescriberLicense: string | null;
  prescriberClinic: string | null;
  prescribedOn: string;
  notes: string | null;
};

export type PharmacyCheck = {
  outcome: PharmacyOutcome;
  /** Pharmacy's own number for the check, e.g. RX-2026-00012. */
  number: string | null;
  note: string | null;
  checkedBy: string | null;
  checkedAt: string | null;
  /** What stops the pharmacist verifying it, in Pharmacy's words. */
  blocking: string[];
  sent: (PrescriptionDetails & { sentBy: string; sentAt: string }) | null;
  syncedAt: string | null;
  /** Why the last answer couldn't be refreshed; the last one is kept. */
  error: string | null;
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
    | "volumeDiscountCentavos"
    | "volumeName"
    | "surchargeCentavos"
    | "surchargeName"
    | "priceSource"
    | "taxCentavos"
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
  volumeDiscountCentavos?: number;
  surchargeCentavos?: number;
  totalCentavos: number;
  approvalReasons: ApprovalReason[];
  priceGroup?: { code: string; name: string } | null;
  tax?: QuoteTax;
  /** Why there's no tax yet (Finance couldn't be asked): saving waits for it. */
  taxError?: string;
  /** Products whose CLIDP has run out, or isn't on file where the division needs one. */
  clidpWarnings?: string[];
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
  team: string;
  teamName: string;
  owner: { id: string | null; name: string | null };
  health: Health;
  status: CompanyStatus;
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
  /** The teams to narrow "team" to: only for a role that reaches every record. */
  teams: Ref[];
  team: string | null;
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

// --- Administration (the CRM's own users, roles, teams and audit log) -------------

/** Whose records a role's permissions reach. */
export type Scope = "own" | "team" | "managed" | "all";

export type AdminUserRow = {
  id: string;
  email: string;
  fullName: string;
  employeeId: string | null;
  isActive: boolean;
  role: { id: string; name: string; scope: Scope };
  team: { id: string; name: string } | null;
  createdAt: string;
  lastSignInAt: string | null;
};

export type PermissionArea = {
  key: string;
  name: string;
  group: string;
  actions: { key: string; label: string; permission: string }[];
};

export type RoleRow = {
  id: string;
  name: string;
  description: string | null;
  scope: Scope;
  isSystem: boolean;
  permissions: string[];
  userCount: number;
};

export type RolesData = {
  roles: RoleRow[];
  catalogue: PermissionArea[];
  scopes: { key: Scope; label: string }[];
};

/** What a person can be given: for whoever manages users, who may not manage roles or teams. */
export type UserOptions = {
  roles: { id: string; name: string; description: string | null; scope: Scope }[];
  teams: { id: string; name: string; isActive: boolean }[];
};

export type TeamRow = {
  id: string;
  name: string;
  description: string | null;
  headquarters: string[];
  isActive: boolean;
  memberCount: number;
  /** The manager over it (above its team lead). */
  manager: { id: string; name: string } | null;
};

export type AuditItem = {
  id: number;
  at: string;
  actor: string;
  actorId: string | null;
  action: string;
  target: string;
  targetType: string | null;
  fields: string[];
};

export type AuditLog = { items: AuditItem[]; more: boolean };

// --- Customers and activities (the CRM's own) ---------------------------------------

export type Ref = { id: string; name: string };
/** A customer type's code ("prospect", "customer"...). The list is an administrator's to keep. */
export type CompanyStatus = string;

export type CustomerTypeColor = "gray" | "brand" | "green" | "blue" | "amber" | "red" | "purple" | "muted";

export type CustomerType = {
  code: string;
  name: string;
  color: CustomerTypeColor;
  sortOrder: number;
  isActive: boolean;
  companies: number;
  /** Which teams are offered it: only these, or everyone but these (both empty: everyone). */
  onlyTeams?: string[];
  exceptTeams?: string[];
};
export type Can = { edit: boolean; delete: boolean };

export type CompanyRow = {
  id: string;
  /** The customer's code (CUS-000001): given by the system, never changed. */
  code: string | null;
  name: string;
  status: CompanyStatus;
  priceGroupCode?: string | null;
  industry: string | null;
  /** How they first came to us: one of the deals' lead sources. */
  leadSource: string | null;
  website: string | null;
  email: string | null;
  phone: string | null;
  city: string | null;
  country: string | null;
  owner: Ref;
  team: Ref | null;
  contactCount: number;
  lastActivityAt: string | null;
  updatedAt: string;
  extra: ExtraValues;
  can: Can;
};

/** Another customer a customer field points at. */
export type CustomerLink = { id: string; name: string; teamName: string | null; canOpen: boolean };

export type CompanyDetail = CompanyRow & {
  /** The customers its customer fields point at (its doctor's hospital), by field key. */
  links: Record<string, CustomerLink>;
  /** Customers in reach that point at this one (the doctors at a hospital). */
  linkedHere: { id: string; name: string; status: string; field: string }[];
  address: string | null;
  notes: string | null;
  createdAt: string;
  contacts: { id: string; name: string; jobTitle: string | null; email: string | null; phone: string | null }[];
  activities: ActivityItem[];
};

export type ContactRow = {
  id: string;
  firstName: string;
  lastName: string | null;
  name: string;
  jobTitle: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  company: Ref | null;
  owner: Ref;
  team: Ref | null;
  lastActivityAt: string | null;
  updatedAt: string;
  extra: ExtraValues;
  can: Can;
};

export type ContactDetail = ContactRow & { notes: string | null; createdAt: string; activities: ActivityItem[] };

export type CrmKind = "call" | "meeting" | "email" | "note" | "task";

export type ActivityItem = {
  id: string;
  kind: CrmKind;
  subject: string;
  body: string | null;
  at: string;
  doneAt: string | null;
  isPlanned: boolean;
  isDone: boolean;
  isOverdue: boolean;
  durationMinutes: number | null;
  direction: "in" | "out" | null;
  /** A planned call: what it's for, and the products to bring up. */
  objective?: string | null;
  /** Where a meeting (or an online call) happens: its Google Meet, Zoom or Teams link. */
  meetingLink?: string | null;
  products?: { code: string; name: string }[];
  /** Once done: what came of it, and the products discussed. */
  outcome?: string | null;
  discussed?: { code: string; name: string }[];
  /** More customers it's about than its own. */
  alsoOn?: Ref[];
  /** An email sent from the person's own email app: a screenshot of it sent is kept as proof. */
  hasProof?: boolean;
  company: Ref | null;
  contact: Ref | null;
  owner: Ref;
  createdAt: string;
  can: Can;
};

export type Paged<T> = { items: T[]; total: number };
export type ActivitySummary = { overdue: number; today: number; upcoming: number; open: number };
export type Assignable = { id: string; name: string; team: Ref | null; isMe: boolean };


// --- the catalogue (Products, Promos, Bundles, Pricing rules) ---

export type CatalogueProduct = Product & { can: { edit: boolean; delete: boolean } };

export type SalesRules = {
  priceTypes: (PriceType & { rule: PriceRule; sortOrder: number })[];
  issuers: Issuer[];
  settings: { discountApprovalBp: number; allowsGuaranteeLetters: boolean; atRiskDays: number; lostDays: number };
  can: { edit: boolean };
};

/** A division (a team) a promo or bundle is for. */
export type DivisionOption = { id: string; name: string };

/** Promos and bundles are per division: only these teams see and quote them. */
type Divided = { teamIds: string[]; teams: DivisionOption[] };

export type PromoRow = Omit<Promo, "divisionCodes" | "startsOn"> & { startsOn: string | null } & Divided;
export type BundleRow = Omit<Bundle, "divisionCodes" | "startsOn"> & { startsOn: string | null } & Divided;

// --- Settings (Administration → Settings) ---

export type CustomEntity = "product" | "company" | "contact" | "quote";
/** Kinds an admin can add. Built-in fields also have their own (status, owner, company). */
export type CustomFieldType =
  | "text"
  | "long_text"
  | "number"
  | "money"
  | "date"
  | "choice"
  | "multi_choice"
  | "yes_no"
  | "email"
  | "phone"
  | "url"
  /** Several of our products, kept as their codes; `options` are the ones it leaves out. */
  | "products"
  /** A generic name, offered from the catalogue's and free to type. */
  | "molecule"
  /** Another customer, kept as its id (a doctor's hospital); `options` are the types it may be. */
  | "customer";

/** One field on a form (Administration → Settings → Forms): built in, or added.
 *  An added field keeps its values in the record's `extra`, by `key`. */
export type FormFieldDef = {
  id: string;
  key: string;
  label: string;
  type: CustomFieldType | "status" | "owner" | "company";
  standard: boolean;
  /** The record can't do without it: always shown, always required. */
  locked: boolean;
  required: boolean;
  hidden: boolean;
  inList: boolean;
  options: string[];
  /** Its choices are kept elsewhere (a customer's lead source: Settings → Deal stages). */
  sharedList?: boolean;
  helpText: string | null;
  placeholder: string | null;
  /** A short option's full name ("MED ONCO": "Medical oncology"): the short one is shown, either is searched. */
  optionNames?: Record<string, string>;
  /** No two records may have the same value in it. */
  unique?: boolean;
  /** Whose records it's on: only these teams', or everyone's but these (both empty: everyone's). */
  onlyTeams?: string[];
  exceptTeams?: string[];
  /** Which customer types it's asked of: only these, or all but these (both empty: every type). */
  onlyTypes?: string[];
  exceptTypes?: string[];
  /** A products or molecule field's choices, from the catalogue. */
  picks?: { value: string; label: string; hint: string }[];
  /** Only in Settings: how many records have a value in it. */
  used?: number;
};
/** The name most places use: a field on a form. */
export type CustomField = FormFieldDef;

export type FormSectionDef = { id: string; title: string; columns: 1 | 2; fields: FormFieldDef[] };
export type FormLayout = { entity: CustomEntity; sections: FormSectionDef[] };

export type ExtraValues = Record<string, string | number | boolean | string[]>;

export type CompanySettings = {
  orgName: string;
  currency: string;
  locale: string;
  timezone: string;
  quotePrefix: string;
  quoteValidDays: number;
  quoteTerms: string | null;
  companyAddress: string | null;
  companyTin: string | null;
  companyContact: string | null;
  currencies: string[];
};

// --- insights (a lead's team, the admin's dashboard) ---

export type PersonInsight = {
  id: string;
  name: string;
  role: string;
  team: Ref | null;
  isMe: boolean;
  overdue: number;
  dueToday: number;
  upcoming: number;
  doneThisWeek: number;
  doneByKind: Partial<Record<CrmKind, number>>;
  lastActivityAt: string | null;
  customers: number;
  newCustomersThisMonth: number;
  quotesThisMonth: number;
  quotedThisMonthCentavos: number;
  quotesWaiting: number;
  quotesRejectedThisMonth: number;
  lastSignInAt: string | null;
  signInsThisWeek: number;
};

export type PeopleInsights = {
  asOf: string;
  monthStart: string;
  people: PersonInsight[];
  totals: {
    people: number;
    signedInThisWeek: number;
    activeThisWeek: number;
    overdue: number;
    dueToday: number;
    doneThisWeek: number;
    customers: number;
    newCustomersThisMonth: number;
    quotesThisMonth: number;
    quotedThisMonthCentavos: number;
    quotesWaiting: number;
  };
};

// --- deals (CRM, decision D2) ---------------------------------------------------------------

export type ForecastCategory = "pipeline" | "best_case" | "commit" | "closed" | "omitted";
export type DealState = "open" | "won" | "lost";

export type DealStage = {
  code: string;
  name: string;
  outcome: DealState;
  probability: number;
  forecastCategory: ForecastCategory;
  sortOrder: number;
  isActive: boolean;
  deals: number;
};

export type DealLists = { sources: string[]; lostReasons: string[] };

export type DealLine = {
  productId: string;
  productCode: string;
  productName: string;
  unit: string;
  quantity: number;
  unitPriceCentavos: number;
  totalCentavos: number;
  /** The promo it's sold under, and what it takes off (since 14 October 2026; older lines have none). */
  promoId?: string | null;
  promoName?: string | null;
  promoDiscountCentavos?: number;
  freeQuantity?: number;
  grossCentavos?: number;
};

export type DealRow = {
  id: string;
  name: string;
  company: { id: string; name: string };
  contact: { id: string; name: string } | null;
  stage: { code: string; name: string };
  state: DealState;
  probability: number;
  forecastCategory: ForecastCategory;
  valueCentavos: number;
  weightedCentavos: number;
  expectedCloseOn: string;
  leadSource: string | null;
  priority: DealPriority | null;
  owner: { id: string; name: string } | null;
  createdBy: { id: string; name: string } | null;
  closedAt: string | null;
  lostReason: string | null;
  competitor: string | null;
  createdAt: string;
  updatedAt: string;
  can: { edit: boolean; delete: boolean; quote: boolean };
};

export type Deal = DealRow & {
  notes: string | null;
  priceType: string | null;
  lines: DealLine[];
  /** Products whose CLIDP has run out, or isn't on file where the division needs one. */
  clidpWarnings?: string[];
  wonQuoteId: string | null;
  quotes: { id: string; number: string; totalCentavos: number; approvalStatus: string; createdAt: string }[];
};

export type DealPriority = "urgent" | "high" | "normal" | "low";

/** In the deals table: the soonest meeting or task still to do with the deal's customer. */
export type DealNextStep = { at: string; kind: "meeting" | "task"; subject: string } | null;

export type DealList = { items: (DealRow & { nextStep: DealNextStep })[]; total: number; valueCentavos: number };

/** The figures and charts above the deals table (/deals-summary). */
export type DealSummary = {
  state: "open" | "closed";
  count: number;
  valueCentavos: number;
  weightedCentavos: number;
  /** Open deals expected to close this month, weighted by probability. */
  thisMonthCentavos: number;
  wonCentavos: number;
  wonCount: number;
  lostCount: number;
  byProbability: { label: string; count: number }[];
  byStage: { code: string; name: string; outcome: "open" | "won" | "lost"; count: number; valueCentavos: number }[];
  byPriority: { priority: DealPriority | null; count: number }[];
};

export type DealBoard = {
  columns: { stage: DealStage; count: number; valueCentavos: number; weightedCentavos: number; deals: DealRow[] }[];
};

export type ForecastFigures = {
  pipelineCentavos: number;
  bestCaseCentavos: number;
  commitCentavos: number;
  wonCentavos: number;
  weightedCentavos: number;
  deals: number;
};

export type DealForecast = {
  period: string;
  label: string;
  start: string;
  end: string;
  people: ({ owner: { id: string; name: string } | null } & ForecastFigures)[];
  totals: ForecastFigures;
};

// --- sales results and revenue targets (CRM) -----------------------------------------------

export type SalesFigures = {
  wonCentavos: number;
  wonCount: number;
  lostCentavos: number;
  lostCount: number;
  /** Won deals as a share of those decided (won or lost); null with none decided. */
  winRate: number | null;
  quotedCentavos: number;
  quoteCount: number;
  targetCentavos: number | null;
  /** Won against the target, as a percentage; null with no target. */
  attainment: number | null;
};

export type SalesResults = {
  period: string;
  label: string;
  start: string;
  end: string;
  view: "mine" | "team";
  totals: SalesFigures;
  people: ({ person: { id: string; name: string }; team: { id: string; name: string } | null } & SalesFigures)[];
  teams: ({ team: { id: string; name: string } | null } & SalesFigures)[];
  customers: { customer: { id: string; name: string }; wonCentavos: number; wonCount: number }[];
  products: { product: { id: string | null; name: string }; quantity: number; wonCentavos: number }[];
  lostReasons: { reason: string; count: number; lostCentavos: number }[];
  canExport: boolean;
};

export type RevenueTargets = {
  month: string;
  people: { person: { id: string; name: string }; team: { id: string; name: string } | null; targetCentavos: number | null }[];
};

// --- possible duplicates (CRM) ---------------------------------------------------------------

export type DuplicateRecord = {
  id: string;
  name: string;
  /** A customer's city and country; a contact's customer. */
  place: string | null;
  email: string | null;
  phone: string | null;
  owner: { id: string; name: string } | null;
  updatedAt: string;
  counts: Record<string, number>;
};

export type DuplicatePairs = {
  kind: "company" | "contact";
  total: number;
  pairs: { score: number; reasons: string[]; a: DuplicateRecord; b: DuplicateRecord }[];
};

// --- KPI management (CRM) ---------------------------------------------------------------------

export type KpiUnit = "count" | "money" | "percent";

export type KpiDef = {
  id: string;
  /** Built-in KPIs have one (revenue_won, doctors_visited...). */
  code: string | null;
  name: string;
  description: string | null;
  /** One of the measures, or "manual" (entered by hand). */
  measure: string;
  measureLabel: string;
  filters: Record<string, string>;
  filterLabel: string | null;
  unit: KpiUnit;
  better: "higher" | "lower";
  /** Empty: everyone. */
  roles: { id: string; name: string }[];
  greenAt: number;
  amberAt: number;
  isActive: boolean;
  builtIn: boolean;
  sortOrder: number;
};

export type KpiMeasure = { key: string; label: string; unit: KpiUnit; about: string; filter: "kind" | "outcome" | "productId" | null };

export type KpiCatalogue = {
  items: KpiDef[];
  measures: KpiMeasure[];
  filterChoices: Record<string, string[]>;
  roles: { id: string; name: string }[];
};

export type KpiTargets = {
  month: string;
  kpis: KpiDef[];
  people: {
    person: { id: string; name: string };
    team: { id: string; name: string } | null;
    role: string;
    roleId: string;
    /** The KPIs that apply to them. */
    applies: string[];
    targets: Record<string, number>;
    /** Results of manual KPIs, entered by hand. */
    entries: Record<string, number>;
  }[];
  teams: { team: { id: string; name: string }; targets: Record<string, number> }[];
};

export type KpiStatus = "green" | "amber" | "red" | "none" | "waiting";

export type KpiResult = {
  actual: number | null;
  target: number | null;
  attainment: number | null;
  /** What should be done by now: the target over the month so far (or the whole target). */
  expected: number | null;
  status: KpiStatus;
  /** A team's: whether the target is its own, not its people's added up. */
  ownTarget?: boolean;
};

export type KpiScorecard = {
  month: string;
  thisMonth: string;
  elapsed: number;
  view: "mine" | "team";
  kpis: KpiDef[];
  people: { person: { id: string; name: string }; team: { id: string; name: string } | null; results: Record<string, KpiResult> }[];
  teams: { team: { id: string; name: string } | null; results: Record<string, KpiResult> }[];
  totals: Record<string, KpiResult>;
  /** The team view shows one role at a time: the roles there are, biggest first, and the one shown. */
  roles: { id: string; name: string; people: number }[];
  role: string | null;
  canSetTargets: boolean;
};
