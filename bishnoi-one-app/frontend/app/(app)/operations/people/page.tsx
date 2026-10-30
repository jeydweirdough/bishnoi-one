// Find a person (Operations, decided 2026-10-29): any email at any company, with where it belongs.
import { FindPerson } from "@/src/modules/console/components/access/operators";
import { PageHeader } from "@/src/platform/ui/sheet";

export const metadata = { title: "Find a person" };

export default function FindPersonPage() {
  return (
    <>
      <PageHeader title="Find a person">
        Any Bishnoi One account by name or email: the company it belongs to, or that it is an operator. Each company changes its own people on People.
      </PageHeader>
      <div className="max-w-4xl">
        <FindPerson />
      </div>
    </>
  );
}
