"use client";

import { useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { FormError, Select } from "@/src/platform/ui/field";
import { receiveTransfer } from "../actions/inventory";
import { useSave } from "./lines";

/** A transfer arrives: which location of the destination it goes into. */
export function ReceiveTransfer({ transferId, locations }: { transferId: string; locations: { id: string; code: string; name: string; isDefault: boolean }[] }) {
  const { pending, error, save } = useSave();
  const [locationId, setLocationId] = useState("");
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="min-w-56">
        <span className="mb-1 block text-meta font-medium text-ink-2">Put it in</span>
        <Select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
          {locations.map((l) => <option key={l.id} value={l.isDefault ? "" : l.id}>{l.code} · {l.name}{l.isDefault ? " (default)" : ""}</option>)}
        </Select>
      </label>
      <Button variant="primary" loading={pending} onClick={() => save(() => receiveTransfer(transferId, { locationId: locationId || null }), () => ({ message: "Received: it's in stock here" }))}>
        Receive transfer
      </Button>
      {error && <div className="w-full"><FormError message={error} /></div>}
    </div>
  );
}
