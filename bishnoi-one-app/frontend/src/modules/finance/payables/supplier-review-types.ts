export type SupplierReviewRow = {
  id: string; name: string; origin: "local" | "foreign" | null; withholding: string | null;
  taxDefaultsConfirmed: boolean; isActive: boolean; version: string;
  companyName: string | null; email: string | null; phone: string | null; owedCentavos: number;
  tin: string | null; branchCode: string | null;
};
export type SupplierReviewList = {
  items: SupplierReviewRow[]; total: number; page: number; pages: number; pageSize: number;
  withholding: { code: string; name: string; rateBp: number }[];
  canAdd: boolean; canEdit: boolean; canDeactivate: boolean;
  reconciliation?: { sourceRows: number; matchedRows: number; createdRows: number; issues: { line: number; code: string | null; name: string | null; tin: string | null; reason: string }[] } | null;
};
export type SupplierReviewChange = { id: string; version: string; origin?: "local" | "foreign"; withholding?: string | null };
