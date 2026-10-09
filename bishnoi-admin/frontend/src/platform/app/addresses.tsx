import { loadAddresses } from "../lib/addresses";
import { AddressesHere } from "./addresses-here";

/** Puts the Platform's addresses where the browser's code reads them (the sidebar's links between apps). */
export async function Addresses() {
  return <AddressesHere value={await loadAddresses()} />;
}
