"use client";

import { useState } from "react";
import { SignInShell } from "./sign-in-shell";
import { FirstPasswordForm } from "./sign-in-forms";
import { TwoStepWelcome } from "./two-step-welcome";

/**
 * What comes before the first page, in order: their own password, then two-step sign-in. Owed (`twoStep`) it can't
 * be skipped; offered (`offer`, 2026-11-01) it can, so nobody has to chase anyone to set it up.
 */
export function FirstSteps({ password, twoStep, offer, next }: { password: boolean; twoStep: boolean; offer: boolean; next: string }) {
  const [step, setStep] = useState<"password" | "twoStep">(password ? "password" : "twoStep");
  const go = () => window.location.assign(next);
  if (step === "password") {
    return (
      <SignInShell title="Choose your own password" intro="You signed in with a password someone gave you. Choose your own before you start: only you will know it.">
        <FirstPasswordForm onDone={() => (twoStep || offer ? setStep("twoStep") : go())} />
      </SignInShell>
    );
  }
  return (
    <SignInShell>
      <TwoStepWelcome skip={twoStep ? null : next} onDone={go} />
    </SignInShell>
  );
}
