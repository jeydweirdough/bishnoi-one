"use client";

import { ChevronDown } from "lucide-react";
import { useId, type ComponentProps, type ReactNode } from "react";

// Underlined fields: transparent, a control-grey rule underneath, the rule
// thickens to ink on focus. The label always sits above, never inside.
const control =
  "block w-full min-w-0 bg-transparent border-0 border-b border-control rounded-none px-0 text-sm text-ink placeholder:text-ink-3/80 focus:outline-none focus:shadow-[inset_0_-1px_0_var(--color-hema)] focus:border-hema aria-[invalid=true]:border-danger disabled:text-ink-3";

type FieldProps = {
  label: string;
  hint?: ReactNode;
  error?: string;
  optional?: boolean;
  className?: string;
  children: (props: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string }) => ReactNode;
};

export function Field({ label, hint, error, optional, className = "", children }: FieldProps) {
  const id = useId();
  const noteId = `${id}-note`;
  const note = error || hint;
  return (
    <div className={`min-w-0 ${className}`}>
      <label htmlFor={id} className="mb-1 block text-meta font-medium text-ink-2">
        {label}
        {optional && <span className="font-normal text-ink-3"> (optional)</span>}
      </label>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": note ? noteId : undefined })}
      {note && (
        <p id={noteId} className={`mt-1 text-meta ${error ? "text-danger" : "text-ink-3"}`}>
          {note}
        </p>
      )}
    </div>
  );
}

export function Input({ className = "", ...rest }: ComponentProps<"input">) {
  return <input className={`h-9 ${control} ${className}`} {...rest} />;
}

/** A file picker drawn like the other fields: the native button, quietened, on the same underline. */
export function FileInput({ className = "", ...rest }: Omit<ComponentProps<"input">, "type">) {
  return (
    <input
      type="file"
      className={`py-1.5 ${control} file:mr-3 file:cursor-pointer file:rounded-[3px] file:border file:border-rule-strong file:bg-sheet file:px-3 file:py-1 file:text-meta file:font-semibold file:text-ink hover:file:border-control ${className}`}
      {...rest}
    />
  );
}

/**
 * A field inside a table cell. The underlined field belongs under a label; a
 * cell has a column header instead, so this one is boxed to show where it can
 * be typed. Always give it an aria-label naming its row and column.
 */
export function CellInput({ className = "", ...rest }: ComponentProps<"input">) {
  return (
    <input
      className={`h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-right text-sm tabular-nums hover:border-control focus:border-hema focus:outline-none aria-[invalid=true]:border-danger ${className}`}
      {...rest}
    />
  );
}

export function Textarea({ className = "", ...rest }: ComponentProps<"textarea">) {
  return <textarea className={`min-h-20 resize-y py-2 ${control} ${className}`} {...rest} />;
}

export function Select({ className = "", children, ...rest }: ComponentProps<"select">) {
  return (
    <div className="relative">
      <select className={`h-9 appearance-none pr-7 ${control} ${className}`} {...rest}>
        {children}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute top-1/2 right-1 size-4 -translate-y-1/2 text-ink-3" />
    </div>
  );
}

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
      <legend className="mb-1.5 text-meta font-medium text-ink-2">{legend}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <label
            key={o.value}
            className="relative inline-flex cursor-pointer items-center gap-1.5 rounded-[3px] border border-rule-strong px-3 py-1.5 text-meta text-ink-2 has-checked:border-hema has-checked:bg-hema-tint has-checked:font-semibold has-checked:text-hema has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-hema"
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="sr-only"
            />
            {o.icon}
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="animate-reshape rounded-[3px] bg-danger-tint px-3 py-2 text-meta text-danger">
      {message}
    </p>
  );
}
