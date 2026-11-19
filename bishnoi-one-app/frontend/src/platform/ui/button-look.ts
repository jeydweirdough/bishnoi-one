// Our button names for shadcn/ui's (2026-11-19), shared by the client Button and server pages' buttonClass:
// the main action solid, the others outlined, quiet as ghost, danger in red.
export type Variant = "primary" | "default" | "quiet" | "danger";
export type Size = "md" | "sm" | "lg";

export const SHAD_VARIANT = { primary: "default", default: "outline", quiet: "ghost", danger: "destructive" } as const;
export const SHAD_SIZE = { md: "lg", sm: "sm", lg: "lg" } as const;
