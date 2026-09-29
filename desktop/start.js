// The starting screen: which app, and what to do if it doesn't come up.
const asked = new URLSearchParams(location.search);
const name = asked.get("name") ?? "Nabhi";

document.title = name;
document.getElementById("name").textContent = name;
document.getElementById("run").textContent = asked.get("run") ?? "";

const SLOW_AFTER_MS = 45_000;
setTimeout(() => (document.getElementById("slow").hidden = false), SLOW_AFTER_MS);
