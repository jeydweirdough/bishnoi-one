import type { Person } from "@/src/modules/console/platform/lib/types";

// A person, as a small square. Their picture if they have one, their initials
// if they don't, in the same ink as the rest of the page: an avatar is a label,
// not a decoration, so it never brings its own colour.

const sizes = {
  sm: "size-7 text-[0.6875rem]",
  md: "size-9 text-meta",
  lg: "size-14 text-base",
  xl: "size-20 text-figure",
} as const;

export type AvatarSize = keyof typeof sizes;

/** "Ana Reyes" -> "AR", "Getmeds" -> "GE", "" -> "?" */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const letters = words.length === 1 ? words[0].slice(0, 2) : `${words[0][0]}${words[words.length - 1][0]}`;
  return letters.toUpperCase();
}

/** The picture's address. `at` (when it last changed) makes a new one load after a change. */
export function photoSrc(id: string, at: string | null | undefined): string | null {
  return at ? `/operations/people/${encodeURIComponent(id)}/photo?v=${encodeURIComponent(at)}` : null;
}

export function Avatar({
  name,
  id,
  photoAt,
  size = "md",
  className = "",
}: {
  name: string;
  id?: string | null;
  photoAt?: string | null;
  size?: AvatarSize;
  className?: string;
}) {
  const src = id ? photoSrc(id, photoAt) : null;
  const shell = `inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full ${sizes[size]} ${className}`;
  if (src) {
    // A plain img: the picture is private, so it must be fetched with the
    // viewer's own session rather than through the image optimiser.
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt="" aria-hidden className={`${shell} border border-rule object-cover`} />;
  }
  return (
    <span aria-hidden className={`${shell} border border-rule bg-bench font-semibold text-ink-2`}>
      {initials(name)}
    </span>
  );
}

/** An avatar with the name beside it, the way people appear in lists. */
export function PersonLine({
  person,
  photoAt,
  detail,
  size = "md",
}: {
  person: Person | { id: string | null; name: string | null };
  photoAt?: string | null;
  detail?: string;
  size?: AvatarSize;
}) {
  const name = person.name ?? "Unassigned";
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <Avatar name={name} id={person.id} photoAt={photoAt} size={size} />
      <span className="min-w-0">
        <span className="block truncate">{name}</span>
        {detail && <span className="block truncate text-meta text-ink-3">{detail}</span>}
      </span>
    </span>
  );
}
