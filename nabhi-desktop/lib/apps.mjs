// The apps inside Nabhi.exe and the ports they run on, on the PC's own address.
//
// The ports are fixed because the screens are built with each other's
// addresses in them (the sidebar's links from CRM to Inventory). They sit high
// and out of the way of common programs; if one is taken, Nabhi.exe says so.

export const HOST = "127.0.0.1";

export const APPS = {
  crm: { name: "Nabhi CRM", folder: "nabhi-crm", web: 47302, api: 47402 },
  inventory: { name: "Nabhi Inventory", folder: "nabhi-inventory", web: 47304, api: 47404 },
};

export const webUrl = (app) => `http://${HOST}:${APPS[app].web}`;
export const apiUrl = (app) => `http://${HOST}:${APPS[app].api}`;

/** The NEXT_PUBLIC_NABHI_*_URL values the screens are built with. */
export function publicUrls() {
  return Object.fromEntries(Object.keys(APPS).map((app) => [`NEXT_PUBLIC_NABHI_${app.toUpperCase()}_URL`, webUrl(app)]));
}
