"use client";

/**
 * The last Ant Design pieces the screens used, drawn with Studio Admin's shadcn/ui parts (2026-11-19). Each takes
 * the props the screens passed to Ant's, so a screen only changes its import. Prefer the shadcn parts in
 * src/components/ui for anything new; these exist so nothing had to be rewritten at once.
 */

import { cn } from "cn";
import { format } from "date-fns";
import dayjs, { type Dayjs } from "dayjs";
import { CalendarIcon, CircleAlert, CircleCheck, Info, Loader2, TriangleAlert } from "lucide-react";
import { useState, type ChangeEvent, type CSSProperties, type ReactElement, type ReactNode } from "react";
import type { DateRange } from "react-day-picker";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/src/components/ui/accordion";
import { Alert as ShadAlert, AlertDescription, AlertTitle } from "@/src/components/ui/alert";
import { Badge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { Calendar } from "@/src/components/ui/calendar";
import { Checkbox as ShadCheckbox } from "@/src/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/src/components/ui/dropdown-menu";
import { Input } from "@/src/components/ui/input";
import { Popover as ShadPopover, PopoverAnchor, PopoverContent, PopoverHeader, PopoverTitle, PopoverTrigger } from "@/src/components/ui/popover";
import { Switch as ShadSwitch } from "@/src/components/ui/switch";
import { Tabs as ShadTabs, TabsContent, TabsList, TabsTrigger } from "@/src/components/ui/tabs";

type Placement = "bottomLeft" | "bottomRight" | "bottom" | "topLeft" | "topRight" | "top" | "left" | "right";
function side(p?: Placement): { side: "top" | "bottom" | "left" | "right"; align: "start" | "end" | "center" } {
  if (!p) return { side: "bottom", align: "start" };
  const s = p.startsWith("top") ? "top" : p === "left" ? "left" : p === "right" ? "right" : "bottom";
  return { side: s, align: p.endsWith("Right") ? "end" : p.endsWith("Left") ? "start" : "center" };
}

// --- Dropdown: a menu opened by its button (DropdownMenu) ------------------------------------------

type MenuItem =
  | { key: string; label: ReactNode; icon?: ReactNode; danger?: boolean; disabled?: boolean; onClick?: () => void; type?: undefined }
  | { type: "divider"; key?: string };
export type MenuProps = { items?: MenuItem[]; onClick?: (info: { key: string }) => void; selectedKeys?: string[] };

export function Dropdown({ menu, placement, disabled, children }: { menu: MenuProps; trigger?: string[]; placement?: Placement; disabled?: boolean; children: ReactElement }) {
  const picked = new Set(menu.selectedKeys ?? []);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild disabled={disabled}>
        {children}
      </DropdownMenuTrigger>
      <DropdownMenuContent {...side(placement)} className="w-auto min-w-44">
        {(menu.items ?? []).map((it, i) =>
          it.type === "divider" ? (
            <DropdownMenuSeparator key={it.key ?? `d${i}`} />
          ) : (
            <DropdownMenuItem
              key={it.key}
              variant={it.danger ? "destructive" : "default"}
              disabled={it.disabled}
              className={cn(picked.has(it.key) && "bg-accent font-medium")}
              onSelect={() => {
                it.onClick?.();
                menu.onClick?.({ key: it.key });
              }}
            >
              {it.icon}
              {it.label}
            </DropdownMenuItem>
          ),
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// --- Popover --------------------------------------------------------------------------------------

export function Popover({
  content,
  title,
  placement,
  open,
  onOpenChange,
  className,
  styles,
  children,
}: {
  content: ReactNode;
  title?: ReactNode;
  trigger?: string;
  placement?: Placement;
  arrow?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
  styles?: { container?: CSSProperties };
  children: ReactElement;
}) {
  return (
    <ShadPopover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent {...side(placement)} className={cn("w-auto", className)} style={styles?.container}>
        {title != null && (
          <PopoverHeader>
            <PopoverTitle>{title}</PopoverTitle>
          </PopoverHeader>
        )}
        {content}
      </PopoverContent>
    </ShadPopover>
  );
}

// --- Segmented: a few choices side by side (shadcn's tabs list) -----------------------------------

type SegOption<T> = T | { value: T; label: ReactNode; disabled?: boolean };

export function Segmented<T extends string = string>({
  value,
  onChange,
  options,
  size,
  block,
  className,
  "aria-label": label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: SegOption<T>[];
  size?: "small" | "middle" | "large";
  block?: boolean;
  className?: string;
  "aria-label"?: string;
}) {
  const opts = options.map((o) => (typeof o === "object" ? o : { value: o, label: o, disabled: false }));
  return (
    <ShadTabs value={value} onValueChange={(v) => onChange(v as T)} className={cn(block ? "w-full" : "w-fit", className)}>
      <TabsList aria-label={label} className={cn(block && "w-full", size === "small" && "h-7")}>
        {opts.map((o) => (
          <TabsTrigger key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </ShadTabs>
  );
}

// --- Tabs: a row of tabs and the one shown ---------------------------------------------------------

export function Tabs({ activeKey, onChange, items, className }: { activeKey: string; onChange: (key: string) => void; items: { key: string; label: ReactNode; children?: ReactNode; disabled?: boolean }[]; className?: string }) {
  return (
    <ShadTabs value={activeKey} onValueChange={onChange} className={className}>
      <TabsList variant="line">
        {items.map((t) => (
          <TabsTrigger key={t.key} value={t.key} disabled={t.disabled}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {items.map((t) => (
        <TabsContent key={t.key} value={t.key}>
          {t.children}
        </TabsContent>
      ))}
    </ShadTabs>
  );
}

// --- Switch and Checkbox ---------------------------------------------------------------------------

export function Switch({ checked, onChange, size, disabled, loading, id, ...rest }: { checked?: boolean; onChange?: (checked: boolean) => void; size?: "small" | "default"; disabled?: boolean; loading?: boolean; id?: string; "aria-label"?: string }) {
  return <ShadSwitch id={id} checked={checked} onCheckedChange={(c) => onChange?.(c)} size={size === "small" ? "sm" : "default"} disabled={disabled || loading} aria-busy={loading || undefined} {...rest} />;
}

/** A tick box with its words beside it; onChange gets { target: { checked } }, as Ant's did. */
export function Checkbox({ checked, disabled, onChange, children, className }: { checked?: boolean; disabled?: boolean; onChange?: (e: { target: { checked: boolean } }) => void; children?: ReactNode; className?: string }) {
  return (
    <label className={cn("inline-flex cursor-pointer items-center gap-2 text-sm has-disabled:cursor-not-allowed has-disabled:opacity-50", className)}>
      <ShadCheckbox checked={checked} disabled={disabled} onCheckedChange={(c) => onChange?.({ target: { checked: c === true } })} />
      {children}
    </label>
  );
}

// --- InputNumber ------------------------------------------------------------------------------------

export function InputNumber({ value, onChange, min, max, disabled, className }: { value?: number | null; onChange?: (n: number | null) => void; min?: number; max?: number; disabled?: boolean; className?: string }) {
  return (
    <Input
      type="number"
      inputMode="numeric"
      min={min}
      max={max}
      disabled={disabled}
      className={cn("tabular-nums", className)}
      value={value ?? ""}
      onChange={(e: ChangeEvent<HTMLInputElement>) => {
        if (e.target.value === "") return onChange?.(null);
        let n = Number(e.target.value);
        if (Number.isNaN(n)) return;
        if (min !== undefined) n = Math.max(min, n);
        if (max !== undefined) n = Math.min(max, n);
        onChange?.(n);
      }}
    />
  );
}

// --- Collapse: sections that open and close (Accordion) -------------------------------------------

export function Collapse({ items, defaultActiveKey, className }: { items: { key: string; label: ReactNode; extra?: ReactNode; children: ReactNode }[]; defaultActiveKey?: string[]; ghost?: boolean; size?: string; className?: string }) {
  return (
    <Accordion type="multiple" defaultValue={defaultActiveKey} className={className}>
      {items.map((it) => (
        <AccordionItem key={it.key} value={it.key}>
          <AccordionTrigger>
            <span className="flex min-w-0 flex-1 items-center justify-between gap-3 pr-2">
              <span className="min-w-0">{it.label}</span>
              {it.extra}
            </span>
          </AccordionTrigger>
          <AccordionContent>{it.children}</AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}

// --- Alert, Tag, Spin -------------------------------------------------------------------------------

const ALERT_ICON = { error: CircleAlert, warning: TriangleAlert, success: CircleCheck, info: Info } as const;

export function Alert({ type = "info", title, description, showIcon, className }: { type?: "error" | "warning" | "success" | "info"; title?: ReactNode; message?: ReactNode; description?: ReactNode; showIcon?: boolean; className?: string }) {
  const Icon = ALERT_ICON[type];
  return (
    <ShadAlert variant={type === "error" ? "destructive" : "default"} className={className}>
      {showIcon && <Icon />}
      {title != null && <AlertTitle>{title}</AlertTitle>}
      {description != null && <AlertDescription>{description}</AlertDescription>}
    </ShadAlert>
  );
}

export function Tag({ color, children, className }: { color?: string; children?: ReactNode; className?: string }) {
  return (
    <Badge variant={color === "error" || color === "red" ? "destructive" : color ? "secondary" : "outline"} className={className}>
      {children}
    </Badge>
  );
}

export function Spin({ size }: { size?: "small" | "default" | "large" }) {
  return <Loader2 role="status" aria-label="Loading" className={cn("animate-spin text-muted-foreground", size === "large" ? "size-8" : size === "small" ? "size-4" : "size-6")} />;
}

// --- AutoComplete: free text with suggestions under it ---------------------------------------------

export function AutoComplete({ id, className, value, onChange, options, placeholder, maxLength, ...rest }: { id?: string; className?: string; value?: string; onChange?: (v: string) => void; options?: { value: string; label?: ReactNode }[]; placeholder?: string; maxLength?: number; status?: string; "aria-describedby"?: string }) {
  const [open, setOpen] = useState(false);
  const list = options ?? [];
  return (
    <ShadPopover open={open && list.length > 0} onOpenChange={setOpen}>
      <PopoverAnchor asChild>
        <Input
          id={id}
          className={className}
          value={value ?? ""}
          placeholder={placeholder}
          maxLength={maxLength}
          autoComplete="off"
          aria-invalid={rest.status === "error" || undefined}
          aria-describedby={rest["aria-describedby"]}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            onChange?.(e.target.value);
            setOpen(true);
          }}
        />
      </PopoverAnchor>
      <PopoverContent align="start" className="w-(--radix-popover-trigger-width) min-w-56 p-1" onOpenAutoFocus={(e) => e.preventDefault()}>
        <div role="listbox" className="max-h-60 overflow-y-auto">
          {list.map((o) => (
            <button
              key={o.value}
              type="button"
              role="option"
              aria-selected={o.value === value}
              className="flex w-full rounded-sm px-2 py-1.5 text-left text-sm hover:bg-muted"
              onClick={() => {
                onChange?.(o.value);
                setOpen(false);
              }}
            >
              {o.label ?? o.value}
            </button>
          ))}
        </div>
      </PopoverContent>
    </ShadPopover>
  );
}

// --- DatePicker.RangePicker: a range on the calendar (days, or whole months) ----------------------

function RangePicker({
  value,
  onChange,
  picker = "date",
  placeholder = ["From", "To"],
  presets = [],
}: {
  value?: [Dayjs, Dayjs] | null;
  onChange?: (dates: [Dayjs, Dayjs] | null) => void;
  picker?: "date" | "month";
  format?: string;
  allowClear?: boolean;
  placeholder?: [string, string];
  presets?: { label: string; value: [Dayjs, Dayjs] }[];
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DateRange | undefined>(value ? { from: value[0].toDate(), to: value[1].toDate() } : undefined);
  const shown = (d: Date) => format(d, picker === "month" ? "MMM yyyy" : "d MMM yyyy");
  const done = (from: Date, to: Date) => {
    const [a, b] = picker === "month" ? [dayjs(from).startOf("month"), dayjs(to).endOf("month")] : [dayjs(from), dayjs(to)];
    onChange?.([a, b]);
    setOpen(false);
  };
  return (
    <ShadPopover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" className={cn("h-8 justify-start px-2.5 font-normal", !value && "text-muted-foreground")}>
          <CalendarIcon data-icon="inline-start" />
          {value ? `${shown(value[0].toDate())} – ${shown(value[1].toDate())}` : `${placeholder[0]} – ${placeholder[1]}`}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="flex w-auto gap-2 p-0" align="start">
        {presets.length > 0 && (
          <div className="flex flex-col gap-1 border-r p-2">
            {presets.map((p) => (
              <Button key={p.label} type="button" variant="ghost" size="sm" className="justify-start" onClick={() => done(p.value[0].toDate(), p.value[1].toDate())}>
                {p.label}
              </Button>
            ))}
          </div>
        )}
        <div>
          <Calendar
            mode="range"
            numberOfMonths={2}
            captionLayout="dropdown"
            defaultMonth={draft?.from}
            selected={draft}
            onSelect={(r) => {
              setDraft(r);
              if (r?.from && r.to && r.from.getTime() !== r.to.getTime()) done(r.from, r.to);
            }}
          />
          {picker === "month" && <p className="px-3 pb-3 text-xs text-muted-foreground">Pick any day in the first and last month: whole months are taken.</p>}
        </div>
      </PopoverContent>
    </ShadPopover>
  );
}

export const DatePicker = { RangePicker };
