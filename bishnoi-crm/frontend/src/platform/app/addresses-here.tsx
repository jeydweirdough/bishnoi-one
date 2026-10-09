"use client";

import { setAddresses, type AppName } from "../lib/apps";

/** Sets the addresses as it's drawn, before the sidebar below it reads them. */
export function AddressesHere({ value }: { value: Partial<Record<AppName, string>> }) {
  setAddresses(value);
  return null;
}
