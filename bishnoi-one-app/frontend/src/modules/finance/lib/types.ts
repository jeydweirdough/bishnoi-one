export type AdminUser = {
  id: string;
  email: string;
  fullName: string;
  isActive: boolean;
  role: { id: string; name: string };
  createdAt: string;
  lastSignInAt: string | null;
};

export type AdminUsers = {
  items: AdminUser[];
  roles: { id: string; name: string; description: string | null }[];
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
  isSystem: boolean;
  permissions: string[];
  userCount: number;
};

export type RolesData = {
  roles: RoleRow[];
  catalogue: PermissionArea[];
};

export type AuditEntry = {
  id: number;
  at: string;
  actor: string;
  actorId: string | null;
  action: string;
  target: string;
  targetType: string | null;
  targetId: string | null;
  fields: string[];
};

export type PageData<T> = {
  items: T[];
  more: boolean;
};


export type * from "@/src/modules/finance/platform/lib/types";
