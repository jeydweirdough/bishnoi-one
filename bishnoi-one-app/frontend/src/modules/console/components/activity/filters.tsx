import Link from "next/link";
import { Button } from "@/src/modules/console/platform/ui/button";
import { Input, Select } from "@/src/modules/console/platform/ui/field";

/** Who did it and which words: a plain form, so the filters live in the URL
 *  and a filtered log can be linked to. The tab it is on rides along. */
export function ActivityFilters({ category, actor, q, actors }: { category: string; actor: string; q: string; actors: string[] }) {
  const people = actor && !actors.some((a) => a.toLowerCase() === actor.toLowerCase()) ? [actor, ...actors] : actors;
  return (
    <form action="/platform/console/activity" method="get" role="search" className="mb-4 flex flex-wrap items-end gap-x-4 gap-y-3">
      {category && <input type="hidden" name="category" value={category} />}
      <label className="block w-full sm:w-56">
        <span className="mb-1 block text-meta font-medium text-ink-2">User</span>
        <Select name="actor" defaultValue={actor}>
          <option value="">All users</option>
          {people.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </Select>
      </label>
      <label className="block w-full sm:w-72">
        <span className="mb-1 block text-meta font-medium text-ink-2">Search</span>
        <Input type="search" name="q" defaultValue={q} placeholder="Name, company or action" />
      </label>
      <div className="flex items-center gap-3">
        <Button type="submit" size="sm">
          Apply
        </Button>
        {(actor || q) && (
          <Link href={category ? `/platform/console/activity?category=${category}` : "/platform/console/activity"} className="text-meta text-ink-2 hover:text-hema hover:underline">
            Clear filters
          </Link>
        )}
      </div>
    </form>
  );
}
