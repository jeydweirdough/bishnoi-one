"use client";

import { Fragment, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Button } from "@/src/components/ui/button";
import { Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/src/components/ui/command";
import { useOneMenu } from "@/src/one/menu/context";
import { Icon, type IconName } from "@/src/platform/ui/icons";

/** Studio Admin's search (Ctrl/⌘ J): every page of the one menu this person has, by group. */
export function SearchMenu() {
  const menu = useOneMenu();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "j" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  if (!menu) return null;
  const groups = [
    { label: "Home", steps: [menu.home] },
    ...menu.processes,
    ...menu.foot,
  ].filter((g) => g.steps.length > 0);

  return (
    <>
      <Button onClick={() => setOpen(true)} variant="link" className="px-0! font-normal text-muted-foreground hover:no-underline">
        <Search data-icon="inline-start" />
        <span className="hidden sm:inline">Search</span>
        <kbd className="hidden h-5 items-center gap-1 rounded border bg-muted px-1.5 text-[10px] font-medium select-none sm:inline-flex">
          <span className="text-xs">Ctrl</span>J
        </kbd>
      </Button>
      <CommandDialog open={open} onOpenChange={setOpen}>
        <Command>
          <CommandInput placeholder="Search pages…" />
          <CommandList>
            <CommandEmpty>No results found.</CommandEmpty>
            {groups.map((g, i) => (
              <Fragment key={g.label}>
                {i > 0 && <CommandSeparator />}
                <CommandGroup heading={g.label}>
                  {g.steps.map((st) => (
                    <CommandItem
                      key={st.href}
                      value={`${g.label} ${st.label}`}
                      onSelect={() => {
                        setOpen(false);
                        router.push(st.href);
                      }}
                    >
                      <Icon name={st.icon as IconName} className="size-4" />
                      <span className="truncate">{st.label}</span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              </Fragment>
            ))}
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
