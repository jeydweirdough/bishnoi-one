"use client";

import { Alert, Input as AntInput, Radio, type InputRef } from "antd";
import { ChevronDown } from "lucide-react";
import { useId, type ComponentProps, type ReactNode, type Ref } from "react";

// Fields are Ant Design's: boxed, Ant's border, blue on focus, red when
// invalid. The label always sits above, never inside.
const control =
  "block w-full min-w-0 rounded-[6px] border border-rule-strong bg-sheet px-[11px] text-sm text-ink placeholder:text-ink-3/70 transition-colors hover:border-hema-hover focus:border-hema focus:outline-none focus:shadow-[0_0_0_2px_rgb(5_145_255_/_0.1)] aria-[invalid=true]:border-[#ff4d4f] disabled:bg-bench disabled:text-ink-3";

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
  className?: string;
  children: (props: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string }) => ReactNode;
};

export function Field({ label, hint, error, optional, className = "", children }: FieldProps) {
  const id = useId();
  const noteId = `${id}-note`;
  const note = error || hint;
  return (
    <div className={`min-w-0 ${className}`}>
      <label htmlFor={id} className="mb-1.5 block text-sm text-ink">
        {label}
        {optional && <span className="font-normal text-ink-3"> (optional)</span>}
      </label>
      {children({ id, "aria-invalid": error ? true : undefined, "aria-describedby": note ? noteId : undefined })}
      {note && (
        <p id={noteId} className={`mt-1 text-meta ${error ? "text-[#ff4d4f]" : "text-ink-3"}`}>
          {note}
        </p>
      )}
    </div>
  );
}

export function Input({ ref, size: _size, ...rest }: ComponentProps<"input">) {
  return (
    <AntInput
      ref={(r: InputRef | null) => toElement(ref, r?.input ?? null)}
      status={rest["aria-invalid"] ? "error" : undefined}
      {...(rest as ComponentProps<typeof AntInput>)}
    />
  );
}

/** A file picker drawn like the other fields: the native button, quietened, on the same underline. */
export function FileInput({ className = "", ...rest }: Omit<ComponentProps<"input">, "type">) {
  return (
    <input
      type="file"
      className={`py-1.5 ${control} file:mr-3 file:cursor-pointer file:rounded-[6px] file:border file:border-rule-strong file:bg-sheet file:px-3 file:py-1 file:text-meta file:font-semibold file:text-ink hover:file:border-control ${className}`}
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
    <AntInput
      ref={(r: InputRef | null) => toElement(ref, r?.input ?? null)}
      status={rest["aria-invalid"] ? "error" : undefined}
      className={`text-right tabular-nums ${className}`}
      {...(rest as ComponentProps<typeof AntInput>)}
    />
  );
}

export function Textarea({ ref, ...rest }: ComponentProps<"textarea">) {
  return (
    <AntInput.TextArea
      ref={(r: { resizableTextArea?: { textArea: HTMLTextAreaElement } } | null) => toElement(ref, r?.resizableTextArea?.textArea ?? null)}
      status={rest["aria-invalid"] ? "error" : undefined}
      {...(rest as ComponentProps<typeof AntInput.TextArea>)}
    />
  );
}

export function Select({ className = "", children, ...rest }: ComponentProps<"select">) {
  return (
    <div className="relative">
      <select className={`h-8 appearance-none pr-8 ${control} ${className}`} {...rest}>
        {children}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute top-1/2 right-2.5 size-3.5 -translate-y-1/2 text-ink-3" />
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
