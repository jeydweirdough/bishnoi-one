"use client";

import { Info } from "lucide-react";
import { plainText } from "@/src/platform/ui/about-tip";
import { Tip } from "@/src/platform/ui/tip";
import { Alert, Input as AntInput, Radio, type InputRef } from "antd";
import { useId, type ComponentProps, type ReactNode, type Ref } from "react";
import { DateInput, type FieldChange } from "./pickers";

// Fields are Ant Design's: boxed, Ant's border, blue on focus, red when
// invalid. The label always sits above, never inside.
const control =
  "block w-full min-w-0 rounded-lg border border-control bg-sheet px-4 text-sm text-ink placeholder:text-ink-3/80 transition-colors hover:border-ink-3 focus:border-ink focus:outline-none focus:shadow-[0_0_0_3px_rgb(168_214_155_/_0.45)] aria-[invalid=true]:border-danger disabled:bg-bench disabled:text-ink-3";

/** Hands the caller the real <input> (or <textarea>), as before, not Ant's wrapper. */
function toElement<E extends HTMLElement>(ref: Ref<E> | undefined, el: E | null) {
  if (typeof ref === "function") ref(el);
  else if (ref) (ref as { current: E | null }).current = el;
}

type FieldProps = {
  label: string;
  hint?: ReactNode;
  error?: string;
  optional?: boolean;
  /** Its width in a FormGrid: sm a code or date, md half, lg most of a row, full the row. */
  size?: FieldSize;
  className?: string;
  children: (props: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string }) => ReactNode;
};

export type FieldSize = "sm" | "md" | "lg" | "full";
const SPAN: Record<FieldSize, string> = { sm: "sm:col-span-2", md: "sm:col-span-3", lg: "sm:col-span-4", full: "sm:col-span-6" };

/**
 * A form's fields, balanced (decided 2026-10-25): six columns on a wide screen, each field as
 * wide as what it takes (a code short, an email half, notes the row), one under another on a phone.
 */
export function FormGrid({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`grid gap-x-4 gap-y-5 sm:grid-cols-6 ${className}`}>{children}</div>;
}

/**
 * One field: its label above, the control, and under it only an error. A plain-words hint sits
 * behind an ⓘ beside the label (decided 2026-10-25), so fields side by side stay the same height
 * and the form reads as a form, not a page of notes; a hint with a link or live part stays under it.
 */
export function Field({ label, hint, error, optional, size, className = "", children }: FieldProps) {
  const id = useId();
  const noteId = `${id}-note`;
  const tip = plainText(hint);
  const below = error || (tip ? null : hint);
  return (
    <div className={`min-w-0 ${size ? SPAN[size] : ""} ${className}`}>
      <div className="mb-1.5 flex items-center gap-1.5">
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
          {optional && <span className="font-normal text-ink-3"> (optional)</span>}
        </label>
        {tip && (
          <Tip tip={tip} className="inline-flex text-ink-3 hover:text-ink">
            <Info className="size-3.5" aria-hidden />
          </Tip>
        )}
      </div>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": error || hint ? noteId : undefined })}
      {below ? (
        <p id={noteId} className={`mt-1 text-meta ${error ? "text-danger" : "text-ink-3"}`}>
          {below}
        </p>
      ) : tip ? (
        <span id={noteId} className="sr-only">
          {tip}
        </span>
      ) : null}
    </div>
  );
}

/** A text field; `prefix` and `suffix` sit inside it (an icon, a unit). */
export function Input({ ref, size: _size, ...rest }: Omit<ComponentProps<"input">, "prefix"> & { prefix?: ReactNode; suffix?: ReactNode; onPressEnter?: () => void; status?: "error" | "warning" | "" }) {
  // Dates and times: the CRM's one picker (the date first, then the time), not the browser's.
  if (rest.type === "date" || rest.type === "datetime-local" || rest.type === "time") {
    const { type, onChange, prefix: _prefix, suffix: _suffix, ...field } = rest;
    return <DateInput {...field} type={type as "date" | "datetime-local" | "time"} onChange={onChange as unknown as (e: FieldChange) => void} />;
  }
  return (
    <AntInput suppressHydrationWarning
      ref={(r: InputRef | null) => toElement(ref, r?.input ?? null)}
      status={rest["aria-invalid"] ? "error" : undefined}
      {...(rest as ComponentProps<typeof AntInput>)}
    />
  );
}

/** A password: hidden as typed, with the eye to show it. */
export function PasswordInput({ ref, size: _size, ...rest }: ComponentProps<"input"> & { status?: "error" | "warning" | "" | string }) {
  return (
    <AntInput.Password suppressHydrationWarning
      ref={(r: InputRef | null) => toElement(ref, r?.input ?? null)}
      status={rest["aria-invalid"] ? "error" : undefined}
      {...(rest as ComponentProps<typeof AntInput.Password>)}
    />
  );
}

/** A search box: the magnifier, and `onSearch` on Enter or its button. */
export function SearchInput(props: ComponentProps<typeof AntInput.Search>) {
  return <AntInput.Search suppressHydrationWarning allowClear {...props} />;
}

/** A file picker drawn like the other fields: the native button, quietened, on the same underline. */
export function FileInput({ className = "", ...rest }: Omit<ComponentProps<"input">, "type">) {
  return (
    <input suppressHydrationWarning
      type="file"
      className={`py-1.5 ${control} file:mr-3 file:cursor-pointer file:rounded-md file:border file:border-rule-strong file:bg-sheet file:px-3 file:py-1 file:text-meta file:font-semibold file:text-ink hover:file:border-control ${className}`}
      {...rest}
    />
  );
}

/**
 * A field inside a table cell. The underlined field belongs under a label; a
 * cell has a column header instead, so this one is boxed to show where it can
 * be typed. Always give it an aria-label naming its row and column.
 */
export function CellInput({ ref, size: _size, className = "", ...rest }: ComponentProps<"input">) {
  return (
    <AntInput suppressHydrationWarning
      ref={(r: InputRef | null) => toElement(ref, r?.input ?? null)}
      status={rest["aria-invalid"] ? "error" : undefined}
      className={`text-right tabular-nums ${className}`}
      {...(rest as ComponentProps<typeof AntInput>)}
    />
  );
}

export function Textarea({ ref, ...rest }: ComponentProps<"textarea">) {
  return (
    <AntInput.TextArea suppressHydrationWarning
      ref={(r: { resizableTextArea?: { textArea: HTMLTextAreaElement } } | null) => toElement(ref, r?.resizableTextArea?.textArea ?? null)}
      status={rest["aria-invalid"] ? "error" : undefined}
      {...(rest as ComponentProps<typeof AntInput.TextArea>)}
    />
  );
}

/** Every dropdown is the CRM's combobox (src/platform/ui/pickers.tsx): typed into to find an option. */
export { Select } from "./pickers";

/** A row of mutually exclusive options that reads like ticks on a form. */
export function Choice<T extends string>({
  name,
  value,
  options,
  onChange,
  legend,
}: {
  name: string;
  value: T;
  options: { value: T; label: string; icon?: ReactNode }[];
  onChange: (value: T) => void;
  legend: string;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-sm text-ink">{legend}</legend>
      <Radio.Group name={name} value={value} onChange={(e) => onChange(e.target.value as T)} optionType="button" buttonStyle="solid">
        {options.map((o) => (
          <Radio.Button key={o.value} value={o.value}>
            <span className="inline-flex items-center gap-1.5">
              {o.icon}
              {o.label}
            </span>
          </Radio.Button>
        ))}
      </Radio.Group>
    </fieldset>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return <Alert role="alert" type="error" showIcon title={message} />;
}
