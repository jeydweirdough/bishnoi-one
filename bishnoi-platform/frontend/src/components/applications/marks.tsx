import type { Deployment } from "@/src/lib/types";

const ENVIRONMENT: Record<Deployment["environment"], string> = { production: "Production", staging: "Staging", development: "Development" };

/** Where a release went. Production is the solid one: it's what people are on. */
export function EnvironmentMark({ environment }: { environment: Deployment["environment"] }) {
  return (
    <span
      className={`inline-flex h-5 items-center rounded-full px-1.5 text-stamp whitespace-nowrap uppercase ${
        environment === "production" ? "border border-ink bg-ink text-white" : "border border-rule-strong text-ink-3"
      }`}
    >
      {ENVIRONMENT[environment]}
    </span>
  );
}
