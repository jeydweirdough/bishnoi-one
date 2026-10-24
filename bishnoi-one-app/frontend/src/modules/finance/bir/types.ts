// What Finance's API answers for the BIR's books, statements, VAT return and summary lists (/finance/bir).

export type Taxpayer = {
  registeredName: string | null;
  tradeName: string | null;
  tin: string | null;
  branchCode: string;
  rdoCode: string | null;
  address: string | null;
  regime: string;
  fiscalMonthEnd: number;
};

export type PeriodOut = { start: string; end: string; label: string };

type Base = { title: string; taxpayer: Taxpayer; period: PeriodOut };

export type SalesJournal = Base & {
  book: "sales-journal";
  rows: {
    date: string; number: string; customer: string; tin: string | null; address: string | null; void: boolean;
    grossCentavos: number; taxableSalesCentavos: number; taxCentavos: number; zeroRatedSalesCentavos: number; exemptSalesCentavos: number; nonTaxableSalesCentavos: number;
  }[];
  totals: { grossCentavos: number; taxableSalesCentavos: number; taxCentavos: number; zeroRatedSalesCentavos: number; exemptSalesCentavos: number; nonTaxableSalesCentavos: number };
};

export type CashReceipts = Base & {
  book: "cash-receipts";
  rows: { date: string; invoice: string; customer: string; tin: string | null; method: string; reference: string | null; cashCentavos: number; cwtCentavos: number; atc: string | null; receivablesCentavos: number }[];
  totals: { cashCentavos: number; cwtCentavos: number; receivablesCentavos: number };
};

export type CashDisbursements = Base & {
  book: "cash-disbursements";
  rows: { date: string; number: string; memo: string; reference: string | null; amountCentavos: number; from: string; charged: { code: string; account: string; debitCentavos: number }[] }[];
  totals: { amountCentavos: number };
};

export type JournalLineOut = { code: string; account: string; debitCentavos: number; creditCentavos: number; description: string | null };

export type GeneralJournal = Base & {
  book: "general-journal";
  entries: { date: string; number: string; memo: string; reference: string | null; source: string; lines: JournalLineOut[] }[];
  totals: { debitCentavos: number; creditCentavos: number };
};

export type GeneralLedger = Base & {
  book: "general-ledger";
  accounts: {
    code: string; account: string; type: string; openingCentavos: number; closingCentavos: number;
    rows: { date: string; number: string; memo: string; debitCentavos: number; creditCentavos: number; balanceCentavos: number }[];
  }[];
};

export type PurchaseJournal = Base & {
  book: "purchase-journal";
  rows: {
    date: string; no: number | null; supplierInvoiceNo: string; supplier: string; tin: string | null; void: boolean; atc: string | null;
    totalCentavos: number; vatableCentavos: number; inputTaxCentavos: number; zeroRatedCentavos: number; exemptCentavos: number; ewtCentavos: number; payableCentavos: number;
  }[];
  totals: { totalCentavos: number; vatableCentavos: number; inputTaxCentavos: number; zeroRatedCentavos: number; exemptCentavos: number; ewtCentavos: number; payableCentavos: number };
};

export type Book = SalesJournal | PurchaseJournal | CashReceipts | CashDisbursements | GeneralJournal | GeneralLedger;

export type StatementLine = { code: string; account: string; amountCentavos: number };

export type IncomeStatement = Base & { income: StatementLine[]; expenses: StatementLine[]; totals: { incomeCentavos: number; expensesCentavos: number; netCentavos: number } };

export type BalanceSheet = {
  title: string; taxpayer: Taxpayer; asOf: string;
  assets: StatementLine[]; liabilities: StatementLine[]; equity: StatementLine[];
  totals: { assetsCentavos: number; liabilitiesCentavos: number; equityCentavos: number; balanced: boolean };
};

export type VatReturn = {
  taxpayer: Taxpayer; period: PeriodOut; year: number; quarter: number;
  form: "2550Q" | "2551Q"; title: string;
  months: { label: string; start: string; end: string; taxableSalesCentavos: number; taxCentavos: number; zeroRatedSalesCentavos: number; exemptSalesCentavos: number; nonTaxableSalesCentavos: number; purchasesCentavos?: number; inputTaxCentavos?: number }[];
  lines: { key: string; label: string; amountCentavos?: number; rateBp?: number; pending?: boolean }[];
  notes: string[];
};

export type SummaryList = {
  list: "sls" | "slp" | "sawt" | "qap"; title: string; taxpayer: Taxpayer; period: PeriodOut; year: number; quarter: number; missingTin: number;
  rows: Record<string, string | number | null | string[]>[];
  totals: Record<string, number>;
};

export type AtcRow = { atc: string | null; nature: string | null; rateBp: number; baseCentavos: number; taxCentavos: number };
export type PayeeRow = AtcRow & { supplierId: string; tin: string | null; payee: string; address: string | null };

export type Withholding2307 = {
  taxpayer: Taxpayer; period: PeriodOut; year: number; quarter: number;
  suppliers: { id: string; name: string; tin: string | null; taxCentavos: number }[];
  certificate?: {
    form: "2307"; title: string;
    payee: { id: string; name: string | null; tin: string | null; address: string | null };
    monthLabels: string[];
    rows: (AtcRow & { months: number[] })[];
    totals: { baseCentavos: number; taxCentavos: number };
  };
};

export type Withholding0619E = { taxpayer: Taxpayer; period: PeriodOut; year: number; month: number; form: "0619E"; title: string; rows: AtcRow[]; totalCentavos: number };

export type Withholding1601EQ = {
  taxpayer: Taxpayer; period: PeriodOut; year: number; quarter: number; form: "1601EQ"; title: string;
  rows: AtcRow[]; totalCentavos: number; remitted: { label: string; amountCentavos: number }[]; dueCentavos: number; notes: string[];
};

export type Withholding1604E = {
  taxpayer: Taxpayer; year: number; form: "1604E"; title: string; period: PeriodOut;
  payees: PayeeRow[]; byAtc: AtcRow[]; totals: { baseCentavos: number; taxCentavos: number };
};

