"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/ant-button";
import { Field, FormError, Input, PasswordInput } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { turnOffTwoStep, type TwoStepState } from "@/src/one/actions";
import { TwoStepSetup } from "@/src/one/sign-in-forms";

/** Two-step sign-in on Your profile (2026-10-30): on or off, set up here, and turned off with the password and a code. */
export function TwoStepCard({ state }: { state: TwoStepState }) {
  const router = useRouter();
  const [setting, setSetting] = useState(false);
  const [turningOff, setTurningOff] = useState(false);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string>();
  const [busy, start] = useTransition();

  return (
    <Sheet id="two-step" className="mt-5 scroll-mt-6 px-5 py-4">
      <SectionTitle icon="password">Two-step sign-in</SectionTitle>
      {state.on ? (
        <div className="mt-2 space-y-3 text-sm text-ink-2">
          <p>
            <span className="rounded-full bg-hema-tint px-2 py-0.5 text-meta font-semibold text-ink">On</span> Each sign-in asks for a code from your authenticator app.{" "}
            {state.recoveryCodesLeft} recovery {state.recoveryCodesLeft === 1 ? "code" : "codes"} left.
          </p>
          {state.required ? (
            <p className="text-meta text-ink-3">Administrators keep it on. New phone? Ask another administrator to reset it on People, then set it up again.</p>
          ) : turningOff ? (
            <form
              className="max-w-sm space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                start(async () => {
                  const r = await turnOffTwoStep(password, code);
                  if (!r.ok) return setError(r.error);
                  toast.success("Two-step sign-in is off");
                  router.refresh();
                });
              }}
            >
              <Field label="Your password">{(p) => <PasswordInput {...p} value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />}</Field>
              <Field label="A code from the app">{(p) => <Input {...p} inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} maxLength={20} />}</Field>
              <FormError message={error} />
              <div className="flex gap-2">
                <Button onClick={() => setTurningOff(false)}>Cancel</Button>
                <Button type="submit" variant="danger" loading={busy}>
                  Turn off
                </Button>
              </div>
            </form>
          ) : (
            <Button size="sm" onClick={() => setTurningOff(true)}>
              Turn off
            </Button>
          )}
        </div>
      ) : setting ? (
        <div className="mt-3 max-w-sm">
          <TwoStepSetup compact onDone={() => (toast.success("Two-step sign-in is on"), router.refresh())} />
        </div>
      ) : (
        <div className="mt-2 space-y-3 text-sm text-ink-2">
          <p>Off. Turn it on so a stolen password alone can&apos;t open your account: each sign-in also asks for a code from an app on your phone.</p>
          <Button variant="primary" size="sm" onClick={() => setSetting(true)}>
            Set up
          </Button>
        </div>
      )}
    </Sheet>
  );
}
