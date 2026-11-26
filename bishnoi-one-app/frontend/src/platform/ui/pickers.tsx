"use client";

import { cn } from "cn";
import { format, isAfter, isBefore, isValid, parse, startOfDay } from "date-fns";
import { CalendarIcon, ChevronsUpDown, Loader2, X } from "lucide-react";
import { Children, isValidElement, useRef, useState, type ComponentProps, type ReactElement, type ReactNode } from "react";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Calendar } from "@/src/components/ui/calendar";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/src/components/ui/command";
import { Input } from "@/src/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/src/components/ui/popover";

// The pickers, one of each, used by every form, built from Studio Admin's shadcn/ui parts (2026-11-19):
// - Select and Combobox: a button opening a searchable list (Popover + Command), shadcn's combobox;
// - DateInput: a button opening the Calendar; a time is the time field; a date and time sit side by side.
// They keep a plain field's shape (value, defaultValue, name, onChange with e.target.value), so a form written
// for the browser's fields works unchanged, and one read with FormData still gets the value under its name.

/** What a change hands the caller: the shape of a plain field's change event. */
export type FieldChange = { target: { value: string; name: string }; currentTarget: { value: string; name: string; form: HTMLFormElement | null } };

function useFieldValue(value: unknown, defaultValue: unknown, name: string | undefined, onChange: ((e: FieldChange) => void) | undefined) {
  const [own, setOwn] = useState(defaultValue === undefined || defaultValue === null ? "" : String(defaultValue));
  const hidden = useRef<HTMLInputElement>(null);
  const controlled = value !== undefined;
  const current = controlled ? (value === null ? "" : String(value)) : own;
  function emit(next: string) {
    if (!controlled) setOwn(next);
    const field = { value: next, name: name ?? "" };
    onChange?.({ target: field, currentTarget: { ...field, form: hidden.current?.form ?? null } });
  }
  // A form read with FormData finds the value under the field's name.
  const formValue = name ? <input suppressHydrationWarning ref={hidden} type="hidden" name={name} value={current} /> : <input suppressHydrationWarning ref={hidden} type="hidden" value={current} />;
  return { current, emit, formValue };
}

// --- the list both dropdowns open ----------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- options carry the caller's own fields (search, teamName…), as Ant's did
type AnyOption = { value?: unknown; label?: ReactNode; disabled?: boolean; options?: AnyOption[]; [key: string]: any };

function textOf(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement(node)) return textOf((node.props as { children?: ReactNode }).children);
  return "";
}

const keyOf = (v: unknown) => (v === undefined || v === null ? "" : String(v));

type ListProps = {
  options: AnyOption[];
  picked: unknown[];
  multiple: boolean;
  onPick: (option: AnyOption) => void;
  /** "label": the list filters itself by label; a function decides per option; false: the caller filters (on the server). */
  filter: "label" | false | ((typed: string, option: AnyOption) => boolean);
  onSearch?: (typed: string) => void;
  notFound?: (typed: string) => ReactNode;
  loading?: boolean;
  optionRender?: (o: { data: AnyOption }) => ReactNode;
  footer?: ReactNode;
};

function PickList({ options, picked, multiple, onPick, filter, onSearch, notFound, loading, optionRender, footer }: ListProps) {
  const [typed, setTyped] = useState("");
  const keys = new Set(picked.map(keyOf));
  const passes = (o: AnyOption) => (typeof filter === "function" ? !typed || filter(typed, o) : true);
  const item = (o: AnyOption) => (
    <CommandItem
      key={keyOf(o.value)}
      value={`${textOf(o.label)} ${keyOf(o.value)}`}
      disabled={o.disabled}
      data-checked={keys.has(keyOf(o.value))}
      onSelect={() => onPick(o)}
    >
      {optionRender ? <span className="min-w-0 flex-1">{optionRender({ data: o })}</span> : <span className="min-w-0 flex-1 truncate">{o.label}</span>}
    </CommandItem>
  );
  return (
    <Command shouldFilter={filter === "label"}>
      <CommandInput
        placeholder="Search…"
        value={typed}
        onValueChange={(t) => {
          setTyped(t);
          onSearch?.(t);
        }}
      />
      <CommandList>
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Loading…
          </div>
        ) : (
          <>
            <CommandEmpty>{notFound ? notFound(typed.trim()) : "No results found."}</CommandEmpty>
            {options.some((o) => o.options)
              ? options.map((g, i) =>
                  g.options ? (
                    <CommandGroup key={`${textOf(g.label)}-${i}`} heading={g.label}>
                      {g.options.filter(passes).map(item)}
                    </CommandGroup>
                  ) : (
                    passes(g) && <CommandGroup key={keyOf(g.value)}>{item(g)}</CommandGroup>
                  ),
                )
              : <CommandGroup>{options.filter(passes).map(item)}</CommandGroup>}
          </>
        )}
      </CommandList>
      {multiple && footer}
    </Command>
  );
}

type TriggerProps = {
  id?: string;
  open: boolean;
  disabled?: boolean;
  className?: string;
  placeholder: string;
  shown: ReactNode;
  /** A filter's name inside the box ("Status:"), as Studio Admin's filters. */
  prefix?: string;
  clear?: () => void;
  aria: Record<string, unknown>;
  autoFocus?: boolean;
  onFocus?: ComponentProps<"button">["onFocus"];
};

function Trigger({ id, open, disabled, className, placeholder, shown, prefix, clear, aria, autoFocus, onFocus }: TriggerProps) {
  const empty = shown === null || shown === undefined || shown === "";
  return (
    <PopoverTrigger asChild>
      <Button
        id={id}
        type="button"
        variant="outline"
        role="combobox"
        aria-expanded={open}
        disabled={disabled}
        autoFocus={autoFocus}
        onFocus={onFocus}
        className={cn("h-8 w-full min-w-0 justify-between px-2.5 font-normal aria-[invalid=true]:border-destructive", className)}
        {...aria}
      >
        {prefix && <span className="shrink-0 text-muted-foreground">{prefix}:</span>}
        <span className={cn("min-w-0 flex-1 truncate text-left", empty && "text-muted-foreground")}>{empty ? placeholder : shown}</span>
        {clear && !empty ? (
          <span
            role="button"
            tabIndex={-1}
            aria-label="Clear"
            className="rounded-sm p-0.5 text-muted-foreground hover:text-foreground"
            onPointerDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
              clear();
            }}
          >
            <X className="size-3.5" />
          </span>
        ) : (
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
        )}
      </Button>
    </PopoverTrigger>
  );
}

// --- Select: written like a plain <select> with <option>s -----------------------------------------

/** The <option>s and <optgroup>s a form wrote, as the list's options. */
function optionsOf(children: ReactNode): AnyOption[] {
  const out: AnyOption[] = [];
  Children.toArray(children).forEach((child) => {
    if (!isValidElement(child)) return;
    const el = child as ReactElement<{ value?: string | number; children?: ReactNode; disabled?: boolean; label?: string }>;
    if (el.type === "option") {
      const label = textOf(el.props.children);
      out.push({ value: el.props.value === undefined ? label : String(el.props.value), label, disabled: el.props.disabled });
    } else if (el.type === "optgroup") {
      out.push({ label: el.props.label ?? "", options: optionsOf(el.props.children) });
    } else {
      out.push(...optionsOf(el.props.children));
    }
  });
  return out;
}

type SelectProps = Omit<ComponentProps<"select">, "onChange" | "size"> & {
  onChange?: (e: FieldChange) => void;
  placeholder?: string;
  /** What the list says when nothing matches what was typed (or there is nothing at all): a way forward, not a dead end. */
  notFound?: (typed: string) => ReactNode;
  /** A filter's name shown inside the box before its value ("Status: Active"). */
  prefix?: string;
};

/** A dropdown, typed into to find an option. Written like a plain <select>, with <option>s. */
export function Select({ children, value, defaultValue, onChange, name, id, disabled, className = "", placeholder, notFound, prefix, required: _required, ...rest }: SelectProps) {
  const { current, emit, formValue } = useFieldValue(value, defaultValue, name, onChange);
  const [open, setOpen] = useState(false);
  const options = optionsOf(children);
  const flat = options.flatMap((o) => o.options ?? [o]);
  const chosen = flat.find((o) => keyOf(o.value) === current);
  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <Trigger
          id={id}
          open={open}
          disabled={disabled}
          className={className}
          placeholder={placeholder ?? "Select"}
          shown={chosen ? chosen.label : current}
          prefix={prefix}
          aria={{ "aria-invalid": rest["aria-invalid"], "aria-describedby": rest["aria-describedby"], "aria-label": rest["aria-label"] }}
        />
        <PopoverContent className="w-(--radix-popover-trigger-width) min-w-48 p-0" align="start">
          <PickList
            options={options}
            picked={[current]}
            multiple={false}
            filter="label"
            notFound={notFound}
            onPick={(o) => {
              emit(keyOf(o.value));
              setOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
      {formValue}
    </>
  );
}

// --- Combobox: the same dropdown, given its options as a list --------------------------------------

type ComboboxProps<V> = {
  options?: AnyOption[];
  value?: V;
  onChange?: (value: V, option?: AnyOption | AnyOption[]) => void;
  mode?: "multiple" | "tags";
  /** Several picks: at most this many. */
  maxCount?: number;
  placeholder?: ReactNode;
  allowClear?: boolean;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  id?: string;
  autoFocus?: boolean;
  onFocus?: ComponentProps<"button">["onFocus"];
  /** As Ant took it: { optionFilterProp, filterOption (false = filtered on the server, or a function), onSearch }. */
  showSearch?: boolean | { optionFilterProp?: string; filterOption?: false | ((input: string, option?: AnyOption) => boolean); onSearch?: (typed: string) => void };
  notFoundContent?: ReactNode;
  optionRender?: (o: { data: AnyOption }) => ReactNode;
  open?: boolean;
  /** Several picks: what the box says when every option is picked ("All divisions"), in place of the first few. */
  allLabel?: string;
  status?: string;
  size?: string;
  "aria-invalid"?: boolean;
  "aria-describedby"?: string;
  "aria-label"?: string;
};

/**
 * The dropdown for a list held in code ({ value, label }): one pick or several (mode="multiple"), searched as typed
 * (by label, or on the server with showSearch's onSearch). Several picks: a tick on each, Clear and Done under the list.
 */
export function Combobox<V = string>({
  className = "",
  options = [],
  value,
  onChange,
  mode,
  maxCount,
  placeholder,
  allowClear,
  disabled,
  loading,
  id,
  autoFocus,
  onFocus,
  showSearch,
  notFoundContent,
  optionRender,
  allLabel,
  ...rest
}: ComboboxProps<V>) {
  const [open, setOpen] = useState(false);
  const multiple = mode === "multiple" || mode === "tags";
  const search = typeof showSearch === "object" ? showSearch : {};
  const filter: ListProps["filter"] = search.filterOption === false ? false : typeof search.filterOption === "function" ? (t, o) => (search.filterOption as (i: string, o?: AnyOption) => boolean)(t, o) : "label";
  const flat = options.flatMap((o) => o.options ?? [o]);
  const picked: unknown[] = multiple ? (Array.isArray(value) ? value : []) : value === undefined || value === null ? [] : [value];
  const labelOf = (v: unknown) => flat.find((o) => keyOf(o.value) === keyOf(v))?.label ?? keyOf(v);

  const pickable = flat.filter((o) => !o.disabled);
  const everything = multiple && pickable.length > 0 && pickable.every((o) => picked.some((v) => keyOf(v) === keyOf(o.value)));
  const shown = multiple ? (
    picked.length === 0 ? null : everything && allLabel ? (
      `${allLabel} (${picked.length})`
    ) : (
      <span className="flex min-w-0 flex-wrap gap-1">
        {picked.slice(0, 2).map((v) => (
          <Badge key={keyOf(v)} variant="secondary" className="max-w-40 truncate">
            {labelOf(v)}
          </Badge>
        ))}
        {picked.length > 2 && <Badge variant="secondary">+{picked.length - 2}</Badge>}
      </span>
    )
  ) : picked.length ? (
    labelOf(picked[0])
  ) : null;

  function pick(o: AnyOption) {
    if (!multiple) {
      onChange?.(o.value as V, o);
      setOpen(false);
      return;
    }
    const k = keyOf(o.value);
    const has = picked.some((v) => keyOf(v) === k);
    if (!has && maxCount !== undefined && picked.length >= maxCount) return;
    const next = has ? picked.filter((v) => keyOf(v) !== k) : [...picked, o.value];
    onChange?.(next as V, flat.filter((x) => next.some((v) => keyOf(v) === keyOf(x.value))));
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Trigger
        id={id}
        open={open}
        disabled={disabled}
        className={className}
        placeholder={typeof placeholder === "string" ? placeholder : "Select"}
        shown={shown}
        autoFocus={autoFocus}
        onFocus={onFocus}
        clear={allowClear ? () => onChange?.((multiple ? [] : undefined) as V, multiple ? [] : undefined) : undefined}
        aria={{ "aria-invalid": rest["aria-invalid"], "aria-describedby": rest["aria-describedby"], "aria-label": rest["aria-label"] }}
      />
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-56 p-0" align="start">
        <PickList
          options={options}
          picked={picked}
          multiple={multiple}
          onPick={pick}
          filter={filter}
          onSearch={search.onSearch}
          notFound={notFoundContent !== undefined ? () => notFoundContent : undefined}
          loading={loading}
          optionRender={optionRender}
          footer={
            <div className="flex items-center justify-between gap-2 border-t p-1.5">
              <span className="flex gap-1">
                {/* Every option at once (not when a limit allows fewer): then take off the few it isn't for. */}
                {maxCount === undefined && (
                  <Button type="button" variant="ghost" size="sm" disabled={everything} onClick={() => onChange?.(pickable.map((o) => o.value) as unknown as V, pickable)}>
                    Select all
                  </Button>
                )}
                <Button type="button" variant="ghost" size="sm" disabled={picked.length === 0} onClick={() => onChange?.([] as unknown as V, [])}>
                  Clear
                </Button>
              </span>
              <Button type="button" size="sm" onClick={() => setOpen(false)}>
                {picked.length ? `Done · ${picked.length}` : "Done"}
              </Button>
            </div>
          }
        />
      </PopoverContent>
    </Popover>
  );
}

// --- dates and times ----------------------------------------------------------------------------

type DateProps = Omit<ComponentProps<"input">, "onChange" | "size" | "type"> & { type: "date" | "datetime-local" | "time"; onChange?: (e: FieldChange) => void };

const toDay = (s: string) => {
  const d = parse(s.slice(0, 10), "yyyy-MM-dd", new Date());
  return isValid(d) ? d : undefined;
};

/** A day, picked on the calendar: shown as people read it (19 Nov 2026). */
function DayButton({ id, day, onPick, disabled, min, max, aria, className }: { id?: string; day: string; onPick: (d: string) => void; disabled?: boolean; min?: unknown; max?: unknown; aria: Record<string, unknown>; className?: string }) {
  const [open, setOpen] = useState(false);
  const d = day ? toDay(day) : undefined;
  const lo = typeof min === "string" && min ? toDay(min) : undefined;
  const hi = typeof max === "string" && max ? toDay(max) : undefined;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button id={id} type="button" variant="outline" disabled={disabled} className={cn("h-8 w-full justify-start px-2.5 font-normal aria-[invalid=true]:border-destructive", !d && "text-muted-foreground", className)} {...aria}>
          <CalendarIcon data-icon="inline-start" />
          {d ? format(d, "d MMM yyyy") : "Date"}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto overflow-hidden p-0" align="start">
        <Calendar
          mode="single"
          selected={d}
          defaultMonth={d}
          captionLayout="dropdown"
          disabled={(x) => Boolean((lo && isBefore(startOfDay(x), lo)) || (hi && isAfter(startOfDay(x), hi)))}
          onSelect={(x) => {
            onPick(x ? format(x, "yyyy-MM-dd") : "");
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}

/** A time: shadcn's time field (as its date-and-time picker uses). */
function TimeBox({ id, value, onChange, disabled, aria, placeholder }: { id?: string; value: string; onChange: (t: string) => void; disabled?: boolean; aria: Record<string, unknown>; placeholder?: string }) {
  return (
    <Input
      id={id}
      type="time"
      step={300}
      value={value}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="appearance-none bg-background [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
      {...aria}
    />
  );
}

/** A date, a time, or a date then a time: picked on the calendar, the time typed. Written like a plain date field. */
export function DateInput({ type, value, defaultValue, onChange, name, id, disabled, min, max, className = "", ...rest }: DateProps) {
  const { current, emit, formValue } = useFieldValue(value, defaultValue, name, onChange);
  const aria = { "aria-invalid": rest["aria-invalid"], "aria-describedby": rest["aria-describedby"], "aria-label": rest["aria-label"] };

  if (type === "time") {
    return (
      <>
        <div className={className}>
          <TimeBox id={id} value={current.slice(0, 5)} onChange={emit} disabled={disabled} aria={aria} />
        </div>
        {formValue}
      </>
    );
  }

  if (type === "date") {
    return (
      <>
        <DayButton id={id} day={current} onPick={emit} disabled={disabled} min={min} max={max} aria={aria} className={className} />
        {formValue}
      </>
    );
  }

  // A date, then its time: the time waits for the date, and starts at 9:00 AM.
  const [day, time] = current ? current.split("T") : ["", ""];
  return (
    <>
      <div className={cn("grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-2", className)}>
        <DayButton id={id} day={day} onPick={(d) => emit(d ? `${d}T${time ? time.slice(0, 5) : "09:00"}` : "")} disabled={disabled} min={min} max={max} aria={aria} />
        <TimeBox value={time ? time.slice(0, 5) : ""} onChange={(t) => day && emit(`${day}T${t || "09:00"}`)} disabled={disabled || !day} aria={{ "aria-label": "Time" }} placeholder={day ? "Time" : "Select a date first"} />
      </div>
      {formValue}
    </>
  );
}

/** A date then its time, for a form that holds the value itself ("2026-10-09T14:30"). */
export function DateTimeField({ value, onChange, id, disabled }: { value: string; onChange: (v: string) => void; id?: string; disabled?: boolean }) {
  return <DateInput type="datetime-local" id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
}
