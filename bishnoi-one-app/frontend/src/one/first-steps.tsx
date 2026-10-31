"use client";

import { useState } from "react";
import { FirstPasswordForm, TwoStepSetup } from "./sign-in-forms";

/** The first sign-in's steps in order: their own password, then two-step sign-in where it's owed, then on. */
export function FirstSteps({ password, twoStep, next }: { password: boolean; twoStep: boolean; next: string }) {
  const [step, setStep] = useState<"password" | "twoStep">(password ? "password" : "twoStep");
  const go = () => window.location.assign(next);
  if (step === "password") return <FirstPasswordForm onDone={() => (twoStep ? setStep("twoStep") : go())} />;
  return (
    <>
      {password && <p className="mt-6 rounded-lg bg-[#f1f7ee] px-4 py-2.5 text-center text-sm text-ink-2">Password saved. One more step: two-step sign-in.</p>}
      <TwoStepSetup onDone={go} />
    </>
  );
}
