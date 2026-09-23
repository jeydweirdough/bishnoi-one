import Link from "next/link";

/** Customers are companies and the contacts in them: one section, two lists. */
export function CustomerTabs({ current }: { current: "companies" | "contacts" }) {
  const tab = (key: "companies" | "contacts", label: string) => (
    <Link
      href={`/${key}`}
      aria-current={key === current ? "page" : undefined}
      className={`-mb-px border-b-2 px-1 pb-2 text-sm ${
        key === current ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"
      }`}
    >
      {label}
    </Link>
  );
  return (
    <nav aria-label="Customers" className="mb-5 flex gap-6 border-b border-rule">
      {tab("companies", "Customers")}
      {tab("contacts", "Contacts")}
    </nav>
  );
}
