"use client";

import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { setBundleActive, setProductActive, setPromoActive } from "../actions/inventory";

/** Switch a product, promo or bundle off (asks first: reps stop seeing it) or back on. Nothing is ever deleted. */
export function SwitchActive({
  kind,
  id,
  name,
  active,
}: {
  kind: "product" | "promo" | "bundle";
  id: string;
  name: string;
  active: boolean;
}) {
  const setActive = { product: setProductActive, promo: setPromoActive, bundle: setBundleActive }[kind];
  const run = async (on: boolean) => {
    const result = await setActive(id, on);
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    toast.success(`${name} switched ${on ? "on" : "off"}`);
  };

  if (!active) {
    return <AsyncButton onRun={async () => void (await run(true))}>Switch on</AsyncButton>;
  }
  return (
    <ConfirmButton
      label="Switch off"
      title={`Switch off ${name}?`}
      body={
        {
          product: "Reps won't be able to put it on new quotes. Quotes that already have it keep their prices.",
          promo: "Reps won't be able to use it on new quotes. Quotes that already used it keep their discount.",
          bundle: "Reps won't be able to put it on new quotes. Quotes that already have it keep the price it came to.",
        }[kind]
      }
      confirmLabel="Switch off"
      onConfirm={() => run(false)}
    />
  );
}
