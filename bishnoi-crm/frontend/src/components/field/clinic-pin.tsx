"use client";

import { MapPin } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { FormError } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { pinClinic, unpinClinic } from "../../actions/field";
import type { Pin } from "./types";
import { locate, mapLink, NO_LOCATION } from "./where";
import { useTerms } from "@/src/components/terms/provider";
import { lower } from "@/src/components/terms/terms";

/**
 * Where the clinic is. An agent pins it standing there, once; after that each
 * visit is shown at the clinic or how far away it was logged. A lead or the
 * admin can take a wrong pin away.
 */
export function ClinicPin({ companyId, pin, canPin, canUnpin, pinnedOn }: { companyId: string; pin: Pin | null; canPin: boolean; canUnpin: boolean; pinnedOn: string | null }) {
  const [error, setError] = useState<string | null>(null);
  const terms = useTerms();
  const site = lower(terms.site);
  const [pending, start] = useTransition();

  function pinHere() {
    start(async () => {
      const found = await locate(15_000);
      if (!found.ok) {
        setError(`${NO_LOCATION[found.why]} Turn it on, then pin the ${site} again.`);
        return;
      }
      const where = found.where;
      const result = await pinClinic(companyId, where);
      if (!result.ok) return setError(result.fields?.accuracyM ?? result.error);
      setError(null);
      toast.success(`${terms.site} pinned`, { description: `To within ${where.accuracyM} m` });
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle icon="visit">{terms.site === "Location" ? "Location" : `${terms.site} location`}</SectionTitle>
      {pin ? (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm">
            <a href={mapLink(pin)} target="_blank" rel="noopener noreferrer" className="text-ink hover:underline">
              See it on the map
            </a>
            {pinnedOn && <span className="block text-meta text-ink-3">Pinned {pinnedOn}</span>}
          </p>
          {canUnpin && (
            <ConfirmButton
              label="Remove pin"
              triggerVariant="quiet"
              triggerSize="sm"
              title={`Remove the ${site}'s pin?`}
              body={`Visits stop being checked against it until an agent pins the ${site} again from there.`}
              confirmLabel="Remove pin"
              onConfirm={async () => {
                const result = await unpinClinic(companyId);
                if (!result.ok) {
                  toast.error(result.error);
                  return false;
                }
                toast.success("Pin removed");
              }}
            />
          )}
        </div>
      ) : (
        <>
          <p className="mt-2 text-meta text-ink-3">Not pinned yet. Pin it once while you&apos;re at the {site}, so each visit can be checked against it.</p>
          {canPin && (
            <Button className="mt-3" size="sm" loading={pending} icon={<MapPin className="size-3.5" aria-hidden />} onClick={pinHere}>
              Pin clinic here
            </Button>
          )}
          <FormError message={error} />
        </>
      )}
    </Sheet>
  );
}
