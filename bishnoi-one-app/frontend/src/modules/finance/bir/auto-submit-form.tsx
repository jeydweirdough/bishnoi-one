"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

/** Filter form that navigates immediately when any <Select> or <select> changes, without waiting for "Show". */
export function AutoSubmitForm({
  action,
  className = "flex flex-wrap items-end gap-3",
  children,
}: {
  action: string;
  className?: string;
  children: ReactNode;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const router = useRouter();

  function navigate(changedName?: string) {
    const form = formRef.current;
    if (!form) return;
    const params = new URLSearchParams();
    for (const [k, v] of new FormData(form).entries()) {
      if (typeof v !== "string" || !v) continue;
      if (changedName === "quarter" && k === "month") continue;
      params.append(k, v);
    }
    const qs = params.toString();
    router.push(qs ? `${action}?${qs}` : action);
  }

  useEffect(() => {
    const form = formRef.current;
    if (!form) return;
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        const target = m.target;
        if (target instanceof HTMLInputElement && target.type === "hidden") {
          navigate(target.name);
          return;
        }
      }
    });
    observer.observe(form, { attributes: true, attributeFilter: ["value"], subtree: true });
    return () => observer.disconnect();
  });

  return (
    <form
      ref={formRef}
      action={action}
      className={className}
      onChange={(e) => {
        if (e.target instanceof HTMLSelectElement) {
          navigate(e.target.name);
        }
      }}
    >
      {children}
    </form>
  );
}
