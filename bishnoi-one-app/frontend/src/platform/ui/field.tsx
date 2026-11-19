"use client";

import { cn } from "cn";
import { CircleAlert, Eye, EyeOff, Info, Loader2, Search, X } from "lucide-react";
import { plainText } from "@/src/platform/ui/about-tip";
import { Tip } from "@/src/platform/ui/tip";
import { useId, useState, type ComponentProps, type KeyboardEvent, type ReactNode } from "react";
import { Alert, AlertTitle } from "@/src/components/ui/alert";
import { Input as ShadInput } from "@/src/components/ui/input";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/src/components/ui/input-group";
import { Textarea as ShadTextarea } from "@/src/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/src/components/ui/toggle-group";
import { DateInput, type FieldChange } from "./pickers";

// Fields are shadcn/ui's, as Studio Admin uses them (2026-11-19): boxed, the theme's border, a ring on focus,
// red when invalid. The label always sits above, never inside.
const control =
  "block w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 text-sm placeholder:text-muted-foreground transition-colors focus-visible:border-ring focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-[invalid=true]:border-destructive disabled:opacity-50";

/** Enter in a field (Ant's onPressEnter), kept for the screens that pass it. */
function withEnter(onPressEnter: (() => void) | undefined, onKeyDown: ComponentProps<"input">["onKeyDown"]) {
  if (!onPressEnter) return onKeyDown;
  return (e: KeyboardEvent<HTMLInputElement>) => {
    onKeyDown?.(e);
    if (e.key === "Enter" && !e.defaultPrevented) onPressEnter();
  };
}

type FieldProps = {
  label: ReactNode;
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
export function Input({
  ref,
  size: _size,
  prefix,
  suffix,
  onPressEnter,
  status: _status,
  onKeyDown,
  className,
  ...rest
}: Omit<ComponentProps<"input">, "prefix"> & { prefix?: ReactNode; suffix?: ReactNode; onPressEnter?: () => void; status?: "error" | "warning" | "" }) {
  // Dates and times: the one picker (the date first, then the time), not the browser's.
  if (rest.type === "date" || rest.type === "datetime-local" || rest.type === "time") {
    const { type, onChange, ...field } = rest;
    return <DateInput {...field} type={type as "date" | "datetime-local" | "time"} onChange={onChange as unknown as (e: FieldChange) => void} />;
  }
  const keyDown = withEnter(onPressEnter, onKeyDown);
  if (prefix == null && suffix == null) return <ShadInput suppressHydrationWarning ref={ref} onKeyDown={keyDown} className={className} {...rest} />;
  return (
    <InputGroup className={className}>
      {prefix != null && <InputGroupAddon>{prefix}</InputGroupAddon>}
      <InputGroupInput suppressHydrationWarning ref={ref} onKeyDown={keyDown} {...rest} />
      {suffix != null && <InputGroupAddon align="inline-end">{suffix}</InputGroupAddon>}
    </InputGroup>
  );
}

/** A password: hidden as typed, with the eye to show it. */
export function PasswordInput({ ref, size: _size, status: _status, className, ...rest }: ComponentProps<"input"> & { status?: "error" | "warning" | "" | string }) {
  const [shown, setShown] = useState(false);
  return (
    <InputGroup className={className}>
      <InputGroupInput suppressHydrationWarning ref={ref} {...rest} type={shown ? "text" : "password"} />
      <InputGroupAddon align="inline-end">
        <InputGroupButton size="icon-xs" aria-label={shown ? "Hide password" : "Show password"} title={shown ? "Hide password" : "Show password"} onClick={() => setShown((v) => !v)}>
          {shown ? <EyeOff /> : <Eye />}
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}

type SearchProps = Omit<ComponentProps<"input">, "size"> & {
  allowClear?: boolean;
  loading?: boolean;
  /** Called with the text on Enter, and with "" when cleared. */
  onSearch?: (value: string) => void;
};

/** A search box: the magnifier, a clear button once something is typed, and `onSearch` on Enter. */
export function SearchInput({ allowClear, loading, onSearch, value, defaultValue, onChange, onKeyDown, className, ...rest }: SearchProps) {
  const [own, setOwn] = useState(String(defaultValue ?? ""));
  const text = value !== undefined ? String(value) : own;
  return (
    <InputGroup className={className}>
      <InputGroupAddon>{loading ? <Loader2 className="animate-spin" /> : <Search />}</InputGroupAddon>
      <InputGroupInput
        suppressHydrationWarning
        type="search"
        value={text}
        onChange={(e) => {
          if (value === undefined) setOwn(e.target.value);
          onChange?.(e);
        }}
        onKeyDown={(e) => {
          onKeyDown?.(e);
          if (e.key === "Enter" && !e.defaultPrevented) onSearch?.(text);
        }}
        {...rest}
      />
      {allowClear && text && (
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            size="icon-xs"
            aria-label="Clear"
            title="Clear"
            onClick={() => {
              if (value === undefined) setOwn("");
              onChange?.({ target: { value: "" }, currentTarget: { value: "" } } as unknown as React.ChangeEvent<HTMLInputElement>);
              onSearch?.("");
            }}
          >
            <X />
          </InputGroupButton>
        </InputGroupAddon>
      )}
    </InputGroup>
  );
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
  return <ShadInput suppressHydrationWarning ref={ref} className={cn("text-right tabular-nums", className)} {...rest} />;
}

export function Textarea({ ref, ...rest }: ComponentProps<"textarea">) {
  return <ShadTextarea suppressHydrationWarning ref={ref} {...rest} />;
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
      <ToggleGroup type="single" variant="outline" spacing={0} value={value} onValueChange={(v) => v && onChange(v as T)} aria-label={legend}>
        {options.map((o) => (
          <ToggleGroupItem key={o.value} value={o.value} name={name} className="data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
            {o.icon}
            {o.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </fieldset>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <Alert variant="destructive">
      <CircleAlert />
      <AlertTitle>{message}</AlertTitle>
    </Alert>
  );
}
