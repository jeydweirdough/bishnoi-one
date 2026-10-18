"use client";

import { TextButton } from "@/src/platform/ui/button";
import { Modal } from "antd";
import { Plus } from "lucide-react";
import { useState, type ReactNode } from "react";

/**
 * "+ Add …" beside a field whose list is missing what's needed: it opens a
 * small form in a popup, and whatever is made there is picked in the field,
 * so the form being filled in isn't left (or lost).
 *
 * The popup is drawn outside the page's own form (a form can't hold another),
 * so its own button saves it, not the form behind it.
 */
export function QuickAdd({ label, title, children }: { label: string; title: string; children: (done: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <TextButton onClick={() => setOpen(true)} className="mt-1 font-semibold">
        <Plus className="size-3.5" aria-hidden />
        {label}
      </TextButton>
      <QuickAddWindow open={open} title={title} onClose={() => setOpen(false)}>
        {children}
      </QuickAddWindow>
    </>
  );
}

/** The quick-add window itself, for a caller that opens it its own way (a picker's "Add … as a customer"). */
export function QuickAddWindow({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: (done: () => void) => ReactNode }) {
  // The CRM's one dialog (Ant's), drawn outside the page's form; its own form's buttons save it.
  return (
    <Modal open={open} title={title} onCancel={onClose} footer={null} width={460} destroyOnHidden>
      {children(onClose)}
    </Modal>
  );
}
