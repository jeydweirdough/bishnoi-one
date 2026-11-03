import type { AccessModule } from "./types";
export type PolicyContext = {
  companyId: string;
  baseRevision: string;
  catalogRevision: string;
  schema: Record<string, unknown>;
  clarificationSchema: Record<string, unknown>;
  semantics: string;
  catalog: { modules: AccessModule[]; abilities: { key: string; label: string; limitMeaning: string | null; grants: Record<string, string[]> }[] };
  roles: { id: string; name: string; isAdmin: boolean; people: number }[];
};
export type PolicyPreview = {
  valid: boolean;
  id?: string;
  expiresAt?: string;
  errors?: string[];
  clarification?: { questions: string[]; unsupported: string[] };
  preview?: {
    semantics: string;
    warnings: string[];
    roles: {
      id: string | null; name: string; operation: string; holders: number;
      beforeAbilities: { key: string; limit: number | null }[];
      afterAbilities: { key: string; limit: number | null }[];
      beforeScopes: Record<string, string | null>; afterScopes: Record<string, string | null>;
      beforeDescription: string | null; afterDescription: string | null;
      rows: { app: string; resource: string; action: string; category: string; permission: string; before: boolean; after: boolean; beforeScope: string | null; afterScope: string | null }[];
    }[];
  };
};
export type PolicyVersion = { id: string; actor: string; appliedAt: string; roles: number };
