import "server-only";
import { ApiError } from "@/src/modules/inventory/platform/lib/api";
import type { Duplicate } from "@/src/modules/inventory/platform/lib/types";

export type Failure = {
  ok: false;
  error: string;
  fields?: Record<string, string>;
  duplicates?: Duplicate[];
};
export type Result<T = null> = { ok: true; data: T } | Failure;

type ValidationItem = { loc?: (string | number)[]; msg?: string };

// The API's wording for the common cases, said the way a person would.
function plainly(message: string): string {
  const short = message.match(/^String should have at least (\d+) characters?$/);
  if (short) return `Use at least ${short[1]} characters.`;
  if (message === "Field required" || message.startsWith("Input should be a valid string")) return "This is required.";
  if (message.startsWith("Input should be a valid date")) return "Select a date.";
  if (message.startsWith("Input should be")) return "Select an option.";
  return message.replace(/^Value error, /, "");
}

/** Turns an API failure into something a form can show: a sentence, plus per-field messages. */
export function toFailure(error: unknown): Failure {
  if (!(error instanceof ApiError)) {
    console.error(error);
    return { ok: false, error: "Something went wrong. Try again." };
  }
  const { status, detail } = error;
  // The API's 401s are already worded for people (wrong password, session ended).
  if (status === 401) return { ok: false, error: typeof detail === "string" ? detail : "Your session ended. Sign in again to continue." };
  if (status === 422 && Array.isArray(detail)) {
    const fields: Record<string, string> = {};
    let general = "";
    for (const item of detail as ValidationItem[]) {
      const loc = (item.loc ?? []).filter((p) => p !== "body");
      const message = plainly(item.msg ?? "Check this field.");
      // A row of a list keeps its path: ["lines", 0, "quantity"] is "lines.0.quantity".
      // Anything else, the innermost name: ["followUp", "title"] belongs to the "title" input.
      const row = loc.findIndex((p) => typeof p === "number");
      const field = row > 0 ? loc.slice(row - 1).join(".") : loc.filter((p): p is string => typeof p === "string").at(-1);
      if (field && !fields[field]) fields[field] = message;
      else if (!field) general ||= message;
    }
    return { ok: false, error: general || "Some fields need attention.", fields };
  }
  if (detail && typeof detail === "object" && "duplicates" in detail) {
    const d = detail as { message: string; duplicates: Duplicate[] };
    return { ok: false, error: d.message, duplicates: d.duplicates };
  }
  return { ok: false, error: typeof detail === "string" ? detail : "Something went wrong. Try again." };
}

export async function attempt<T>(work: () => Promise<T>): Promise<Result<T>> {
  try {
    return { ok: true, data: await work() };
  } catch (error) {
    return toFailure(error);
  }
}
