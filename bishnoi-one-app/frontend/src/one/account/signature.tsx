"use client";

import { SignatureCard } from "@/src/platform/signature/card";
import { removeMySignature, saveMySignature, type PlatformSignature } from "./signature-actions";

/** Your e-signature on your profile: one for every app (feature plan step 10). */
export function MySignatureCard({ signature }: { signature: PlatformSignature }) {
  const data = {
    current: signature.has && signature.image && signature.setAt ? { image: signature.image, method: signature.method ?? "drawn", setAt: signature.setAt } : null,
    confirmBy: "password" as const,
    recentSignIn: false,
  };
  return (
    <SignatureCard
      data={data}
      save={saveMySignature}
      remove={removeMySignature}
      intro="One signature for every app: it is placed on the documents you prepare, approve, review or settle, with your name, the date and a reference to what you signed. Only you can set it; documents you already signed keep the signature they were signed with."
    />
  );
}
