// What /pricing/rules sends: the order a quote line is priced in, price
// groups, and the dated rules (benchmarks/decisions.md, D4).

export type ConditionKind = "group_price" | "volume" | "surcharge";

export type PriceRule = {
  id: string;
  kind: ConditionKind;
  name: string;
  product: { id: string; name: string } | null;
  priceGroup: { code: string; name: string } | null;
  priceType: string | null;
  amountCentavos: number | null;
  percentBp: number | null;
  tiers: { minQty: number; percentBp: number }[];
  startsOn: string | null;
  endsOn: string | null;
  isActive: boolean;
  state: "running" | "upcoming" | "ended" | "off";
  running: boolean;
  updatedAt: string;
};

export type Procedure = { price: string[]; adjust: string[]; tax: boolean };

export type PriceRules = {
  procedure: Procedure;
  sources: { key: string; name: string }[];
  adjustments: { key: string; name: string }[];
  pricesIncludeTax: boolean;
  financeLinked: boolean;
  groups: { code: string; name: string; isActive: boolean; customers: number }[];
  conditions: PriceRule[];
  today: string;
  can: { edit: boolean };
};

export const SOURCE_WORDS: Record<string, string> = {
  group_price: "Customer-group price",
  team_price: "Team price",
  list_price: "List price",
  entered: "Entered by the rep",
};
