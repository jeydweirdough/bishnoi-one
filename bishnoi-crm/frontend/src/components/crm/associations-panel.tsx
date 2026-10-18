import { load } from "@/src/platform/lib/api";
import type { AssocKind, Associations } from "../../actions/associations";
import { AssociationsCard } from "./associations-card";

/** A record's associations, loaded on their own so the page never waits for them. */
export async function AssociationsPanel({ kind, id }: { kind: AssocKind; id: string }) {
  const data = await load<Associations>(`/associations?type=${kind}&id=${encodeURIComponent(id)}`).catch(() => null);
  return data ? <AssociationsCard kind={kind} id={id} data={data} /> : null;
}
