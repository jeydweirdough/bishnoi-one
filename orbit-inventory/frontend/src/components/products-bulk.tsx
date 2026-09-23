"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { bulkProducts } from "../actions/bulk";
import { plural, toBasisPoints } from "@/src/platform/lib/format";
import { BulkBar, BulkStep, useBulkRun, useSelection } from "@/src/platform/bulk/selection";

const NOUN: [string, string] = ["product", "products"];

export function ProductsBulk({ state, priceTypes }: { state: "active" | "off"; priceTypes: { code: string; name: string }[] }) {
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [repricing, setRepricing] = useState(false);
  const many = plural(s.ids.length, ...NOUN);

  if (state === "off") {
    return (
      <BulkBar noun={NOUN}>
        <Button
          size="sm"
          variant="primary"
          loading={running}
          onClick={() => run({ doing: "Switching on", did: (n) => `${plural(n, ...NOUN)} back on sale` }, (ids) => bulkProducts(ids, { action: "activate" }))}
        >
          Switch on
        </Button>
      </BulkBar>
    );
  }

  const reprice = (
    <BulkStep
      submitLabel={`Change ${many}`}
      onCancel={() => setRepricing(false)}
      onSubmit={async (form) => {
        const bp = toBasisPoints(String(form.get("percent") ?? ""));
        const down = form.get("direction") === "down";
        if (!bp || bp > (down ? 9000 : 10000)) {
          toast.error(down ? "Lower by more than 0% and at most 90%." : "Raise by more than 0% and at most 100%.");
          return false;
        }
        const code = String(form.get("priceType") ?? "");
        const which = priceTypes.find((t) => t.code === code)?.name ?? "Prices";
        const by = `${down ? "down" : "up"} ${bp / 100}%`;
        await run({ doing: "Changing prices", did: (n) => `${which} ${by} on ${plural(n, ...NOUN)}` }, (ids) =>
          bulkProducts(ids, { action: "reprice", changeBp: down ? -bp : bp, priceType: code || null }),
        );
      }}
    >
      <Field label="Price" className="w-44">
        {(p) => (
          <Select {...p} name="priceType" defaultValue="" autoFocus>
            <option value="">Every list price</option>
            {priceTypes.map((t) => (
              <option key={t.code} value={t.code}>
                {t.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Change" className="w-28">
        {(p) => (
          <Select {...p} name="direction" defaultValue="up">
            <option value="up">Raise by</option>
            <option value="down">Lower by</option>
          </Select>
        )}
      </Field>
      <Field label="Percent" className="w-24">
        {(p) => <Input {...p} name="percent" inputMode="decimal" placeholder="5" required />}
      </Field>
    </BulkStep>
  );

  return (
    <BulkBar noun={NOUN} step={repricing ? reprice : undefined}>
      <Button size="sm" variant="primary" disabled={running} onClick={() => setRepricing(true)}>
        Change prices
      </Button>
      <Button
        size="sm"
        loading={running}
        onClick={() => run({ doing: "Switching off", did: (n) => `${plural(n, ...NOUN)} switched off` }, (ids) => bulkProducts(ids, { action: "deactivate" }))}
      >
        Switch off
      </Button>
    </BulkBar>
  );
}
