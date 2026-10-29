"use client";

import { SignatureCard as Shared } from "@/src/platform/signature/card";
import { removeSignature, setSignature } from "@/src/modules/finance/signature/actions";
import type { MySignature } from "@/src/modules/finance/signature/types";

// Your e-signature in Finance (decided 2026-10-22): the shared card (src/platform/signature/, step 10) with
// Finance's save and remove. Finance places it on the documents you prepare, approve, review or settle; without
// one here, Finance uses your Bishnoi One signature (from your profile in the Admin Console).

export function SignatureCard({ data }: { data: MySignature }) {
  return (
    <Shared
      data={data}
      save={setSignature}
      remove={removeSignature}
      intro={
        <>
          Finance places it on the documents you prepare, approve, review or settle (journal vouchers, liquidation reports), with your name, the date and a reference. Without one
          here, Finance uses the signature on your Bishnoi One profile.
        </>
      }
    />
  );
}
