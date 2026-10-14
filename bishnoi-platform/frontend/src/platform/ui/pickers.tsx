"use client";

import { DatePicker, Select as AntSelect, TimePicker, type SelectProps as AntSelectProps } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import { Children, isValidElement, useRef, useState, type ComponentProps, type ReactElement, type ReactNode } from "react";

dayjs.extend(customParseFormat);

// The CRM's pickers, one of each, used by every form:
// - Select: a combobox, typed into to find an option, in place of the browser's list;
// - DateField, TimeField, DateTimeField: the date first, then the time beside it, each typed or picked.
// They keep a plain field's shape (value, defaultValue, name, onChange with
// e.target.value), so a form written for the browser's fields works unchanged,
// and one read with FormData still gets the value under its name.

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

// --- Select: a searchable combobox -------------------------------------------------------------

type Option = { value: string; label: string; disabled?: boolean };
type Group = { label: string; options: Option[] };
// An empty value ("No one in particular", "Not said") gets one of its own: Ant reads "" as nothing chosen.
const EMPTY = "__empty__";

function textOf(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement(node)) return textOf((node.props as { children?: ReactNode }).children);
  return "";
}

/** The <option>s and <optgroup>s a form wrote, as the combobox's options. */
function optionsOf(children: ReactNode): (Option | Group)[] {
  const out: (Option | Group)[] = [];
  Children.toArray(children).forEach((child) => {
    if (!isValidElement(child)) return;
    const el = child as ReactElement<{ value?: string | number; children?: ReactNode; disabled?: boolean; label?: string }>;
    if (el.type === "option") {
      const label = textOf(el.props.children);
      const raw = el.props.value === undefined ? label : String(el.props.value);
      out.push({ value: raw === "" ? EMPTY : raw, label, disabled: el.props.disabled });
    } else if (el.type === "optgroup") {
      out.push({ label: el.props.label ?? "", options: optionsOf(el.props.children) as Option[] });
    } else {
      out.push(...optionsOf(el.props.children));
    }
  });
  return out;
}

type SelectProps = Omit<ComponentProps<"select">, "onChange" | "size"> & { onChange?: (e: FieldChange) => void; placeholder?: string };

/** A dropdown, typed into to find an option. Written like a plain <select>, with <option>s. */
export function Select({ children, value, defaultValue, onChange, name, id, disabled, className = "", placeholder, required: _required, ...rest }: SelectProps) {
  const { current, emit, formValue } = useFieldValue(value, defaultValue, name, onChange);
  const options = optionsOf(children);
  const flat = options.flatMap((o) => ("options" in o ? o.options : [o]));
  const shown = current === "" ? (flat.some((o) => o.value === EMPTY) ? EMPTY : undefined) : current;
  return (
    <>
      <AntSelect
        id={id}
        className={`w-full ${className}`}
        value={shown}
        onChange={(v: string | undefined) => emit(v === undefined || v === EMPTY ? "" : v)}
        options={options}
        disabled={disabled}
        placeholder={placeholder ?? "Select"}
        showSearch={{ optionFilterProp: "label" }}
        status={rest["aria-invalid"] ? "error" : undefined}
        aria-invalid={rest["aria-invalid"]}
        aria-describedby={rest["aria-describedby"]}
        aria-label={rest["aria-label"]}
        popupMatchSelectWidth
      />
      {formValue}
    </>
  );
}

// --- Combobox: the same dropdown, given its options as a list --------------------------------------

/**
 * The CRM's dropdown for a list held in code ({ value, label }): one pick or
 * several (mode="multiple"), searched as typed (by label, or on the server with
 * showSearch's onSearch). The same look and defaults as Select; a "" option
 * reads as a choice, not as nothing.
 */
export function Combobox<V = string>({ className = "", options, value, onChange, showSearch, placeholder, ...rest }: AntSelectProps<V>) {
  const single = rest.mode !== "multiple" && rest.mode !== "tags";
  const hasEmpty = single && (options ?? []).some((o) => (o as { value?: unknown }).value === "");
  const mapped = hasEmpty ? (options ?? []).map((o) => ((o as { value?: unknown }).value === "" ? { ...o, value: EMPTY } : o)) : options;
  return (
    <AntSelect<V>
      className={`w-full ${className}`}
      options={mapped as AntSelectProps<V>["options"]}
      value={(hasEmpty && value === "" ? EMPTY : value) as V}
      onChange={(v, o) => onChange?.((hasEmpty && (v as unknown) === EMPTY ? "" : v) as V, o)}
      showSearch={showSearch ?? { optionFilterProp: "label" }}
      placeholder={placeholder ?? (single ? "Select" : "Select one or more")}
      popupMatchSelectWidth
      {...rest}
    />
  );
}

// --- dates and times ----------------------------------------------------------------------------

// Shown as people read them; typed in any of these.
const DAY_FORMATS = ["D MMM YYYY", "D MMMM YYYY", "YYYY-MM-DD", "M/D/YYYY", "D/M/YYYY"];
const TIME_FORMATS = ["h:mm A", "h:mmA", "H:mm", "h A"];

type DateProps = Omit<ComponentProps<"input">, "onChange" | "size" | "type"> & { type: "date" | "datetime-local" | "time"; onChange?: (e: FieldChange) => void };

function limits(min: unknown, max: unknown) {
  const lo = typeof min === "string" && min ? dayjs(min.slice(0, 10)) : null;
  const hi = typeof max === "string" && max ? dayjs(max.slice(0, 10)) : null;
  return (d: Dayjs) => Boolean((lo && d.isBefore(lo, "day")) || (hi && d.isAfter(hi, "day")));
}

/** A date, a time, or a date then a time: typed or picked. Written like a plain date field. */
export function DateInput({ type, value, defaultValue, onChange, name, id, disabled, min, max, className = "", ...rest }: DateProps) {
  const { current, emit, formValue } = useFieldValue(value, defaultValue, name, onChange);
  const status = rest["aria-invalid"] ? ("error" as const) : undefined;
  const aria = { "aria-invalid": rest["aria-invalid"], "aria-describedby": rest["aria-describedby"], "aria-label": rest["aria-label"] };
  const outside = limits(min, max);

  if (type === "time") {
    const t = current ? dayjs(current, "HH:mm") : null;
    return (
      <>
        <TimePicker id={id} className={`w-full ${className}`} value={t} onChange={(d) => emit(d ? d.format("HH:mm") : "")} format={TIME_FORMATS} use12Hours minuteStep={5} needConfirm={false} disabled={disabled} status={status} placeholder="Time" {...aria} />
        {formValue}
      </>
    );
  }

  if (type === "date") {
    const d = current ? dayjs(current.slice(0, 10)) : null;
    return (
      <>
        <DatePicker id={id} className={`w-full ${className}`} value={d} onChange={(x) => emit(x ? x.format("YYYY-MM-DD") : "")} format={DAY_FORMATS} disabledDate={outside} disabled={disabled} status={status} placeholder="Date" {...aria} />
        {formValue}
      </>
    );
  }

  // A date, then its time: the time waits for the date, and starts at 9:00 AM.
  const [day, time] = current ? current.split("T") : ["", ""];
  const d = day ? dayjs(day) : null;
  const t = time ? dayjs(time.slice(0, 5), "HH:mm") : null;
  return (
    <>
      <div className={`grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-2 ${className}`}>
        <DatePicker
          id={id}
          className="w-full"
          value={d}
          onChange={(x) => emit(x ? `${x.format("YYYY-MM-DD")}T${time ? time.slice(0, 5) : "09:00"}` : "")}
          format={DAY_FORMATS}
          disabledDate={outside}
          disabled={disabled}
          status={status}
          placeholder="Date"
          {...aria}
        />
        <TimePicker
          className="w-full"
          value={t}
          onChange={(x) => day && emit(`${day}T${x ? x.format("HH:mm") : "09:00"}`)}
          format={TIME_FORMATS}
          use12Hours
          minuteStep={5}
          needConfirm={false}
          disabled={disabled || !day}
          status={status}
          placeholder={day ? "Time" : "Select a date first"}
          aria-label="Time"
        />
      </div>
      {formValue}
    </>
  );
}

/** A date then its time, for a form that holds the value itself ("2026-10-09T14:30"). */
export function DateTimeField({ value, onChange, id, disabled }: { value: string; onChange: (v: string) => void; id?: string; disabled?: boolean }) {
  return <DateInput type="datetime-local" id={id} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
}
