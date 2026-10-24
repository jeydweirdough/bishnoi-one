// What Finance's tax API sends. Money is in centavos; rates in basis points (1200 = 12%).

export type TaxProfile = {
  country: string;
  countryName: string;
  regime: string;
  regimeName: string;
  registeredName: string | null;
  tradeName: string | null;
  tin: string | null;
  branchCode: string;
  registeredAddress: string | null;
  pricesIncludeTax: boolean;
  rdoCode: string | null;
  fiscalMonthEnd: number;
  complete: boolean;
  updatedAt: string | null;
};

export type TaxRateRow = { id: number; rateBp: number; validFrom: string; validTo: string | null; source: "pack" | "admin"; basis: string | null };

export type TaxCode = {
  code: string;
  name: string;
  bucket: "taxable" | "zero_rated" | "exempt" | "non_taxable";
  rated: boolean;
  rateTodayBp: number | null;
  rates: TaxRateRow[];
};

export type Option = { key: string; name: string };

export type TaxSetup = {
  profile: TaxProfile;
  countries: { code: string; name: string }[];
  pack: {
    country: string;
    name: string;
    document: string;
    regimes: Option[];
    categories: Option[];
    treatments: (Option & { needsId: boolean })[];
    codes: TaxCode[];
  };
  today: string;
  canEdit: boolean;
};

export type SaleLineInput = {
  description: string | null;
  quantity: number;
  unitPriceCentavos: number;
  discountCentavos: number;
  category: string;
  reliefEligible: boolean;
};

export type SaleInput = {
  treatment: string;
  on: string | null;
  pricesIncludeTax: boolean | null;
  buyer: { name: string | null; tin: string | null; address: string | null; idNumber: string | null } | null;
  lines: SaleLineInput[];
};

export type ComputedSale = {
  document: string;
  on: string;
  pricesIncludeTax: boolean;
  seller: { registeredName: string | null; tradeName: string | null; tin: string | null; address: string | null; regime: string; regimeName: string };
  buyer: { name: string | null; tin: string | null; address: string | null; idNumber: string | null };
  treatment: Option;
  lines: {
    description: string | null;
    code: string;
    codeName: string;
    bucket: TaxCode["bucket"];
    rateBp: number;
    priceCentavos: number;
    baseCentavos: number;
    reliefCentavos: number;
    taxableCentavos: number;
    taxCentavos: number;
    totalCentavos: number;
  }[];
  summary: { key: string; label: string; amountCentavos: number }[];
  relief: { label: string; amountCentavos: number } | null;
  totalDueCentavos: number;
  sellerTax: { code: string; name: string; rateBp: number; amountCentavos: number } | null;
  notice: string | null;
  warnings: string[];
};
