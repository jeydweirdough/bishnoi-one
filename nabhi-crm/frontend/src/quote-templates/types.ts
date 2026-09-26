// Quotation templates: set up by an admin under Settings, used on a quote's print page.

export type TemplateDesign = {
  companyName: string;
  address: string;
  phone: string;
  tin: string;
  vat: "vat" | "non_vat";
  payableTo: string;
  heading: string;
  customerLabel: string;
  certification: string;
  acceptance: string;
  notes: string;
  signatoryName: string;
  signatoryTitle: string;
  signatoryContact: string;
};

export type QuoteTemplate = {
  id: string;
  name: string;
  kind: "form" | "excel";
  payer: string | null;
  payerName: string | null;
  teamId: string | null;
  teamName: string | null;
  isActive: boolean;
  controlPrefix: string | null;
  controlNext: number;
  controlDigits: number;
  controlExample: string;
  design: TemplateDesign;
  hasLogo: boolean;
  hasSignature: boolean;
  excel: { name: string; sheet: string; sheets: string[]; found: string[]; missing: string[] } | null;
  updatedAt: string;
};

export type TemplateList = {
  items: QuoteTemplate[];
  issuers: { code: string; name: string }[];
  teams: { id: string; name: string }[];
  placeholders: { key: string; label: string }[];
  designDefaults: TemplateDesign;
};

export type DocumentLine = {
  no: number;
  generic: string;
  brand: string;
  product: string;
  strength: string;
  form: string;
  unit: string;
  qty: number;
  free: number;
  price: number;
  discount: number | null;
  net: number;
  total: number;
};

export type QuoteDocument = {
  template: QuoteTemplate;
  controlNumber: string;
  quoteNumber: string;
  date: string;
  validUntil: string | null;
  customer: string;
  phone: string;
  address: string;
  hospital: string;
  issuer: string;
  letterNumber: string;
  letterAmount: number | null;
  team: string;
  preparedBy: string;
  lines: DocumentLine[];
  total: number;
  tax: { summary: { key: string; label: string; amountCentavos: number }[]; pricesIncludeTax: boolean } | null;
  notes: string;
  terms: string;
  design: TemplateDesign;
};
