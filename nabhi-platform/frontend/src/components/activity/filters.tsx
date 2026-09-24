import Link from "next/link";
import { Button } from "@/src/platform/ui/button";
import { Input, Select } from "@/src/platform/ui/field";

/** Who did it and which words: a plain form, so the filters live in the URL
 *  and a filtered log can be linked to. The tab it is on rides along. */
export function ActivityFilters({ category, actor, q, actors }: { category: string; actor: string; q: string; actors: string[] }) {
  const people = actor && !actors.some((a) => a.toLowerCase() === actor.toLowerCase()) ? [actor, ...actors] : actors;
  return (
    <form action="/activity" method="get" role="search" className="mb-4 flex flex-wrap items-end gap-x-4 gap-y-3">
      {category && <input type="hidden" name="category" value={category} />}
      <label className="block w-full sm:w-56">
        <span className="mb-1 block text-meta font-medium text-ink-2">Who</span>
        <Select name="actor" defaultValue={actor}>
          <option value="">Anyone</option>
          {people.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </Select>
      </label>
      <label className="block w-full sm:w-72">
        <span className="mb-1 block text-meta font-medium text-ink-2">Words</span>
        <Input type="search" name="q" defaultValue={q} placeholder="A name, a company, an action" />
      </label>
      <div className="flex items-center gap-3">
        <Button type="submit" size="sm">
          Show
        </Button>
        {(actor || q) && (
          <Link href={category ? `/activity?category=${category}` : "/activity"} className="text-meta text-ink-2 hover:text-hema hover:underline">
            Clear filters
          </Link>
        )}
      </div>
    </form>
  );
}
