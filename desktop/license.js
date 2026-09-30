// The license screen: set it up on this PC, or say what's wrong with it.
// What to show comes in the address (?view=activate|problem&app=...&company=...&error=...).
const $ = (id) => document.getElementById(id);
const asked = new URLSearchParams(location.search);
const view = asked.get("view") === "problem" ? "problem" : "activate";
let fileText = null;

document.title = `${asked.get("app") ?? "Nabhi"}: license`;
$(view).hidden = false;

function readFile(input) {
  return new Promise((resolve, reject) => {
    const f = input.files?.[0];
    if (!f) return resolve(null);
    if (f.size > 64 * 1024) return reject(new Error("That file is too large to be a Nabhi license file."));
    const reader = new FileReader();
    reader.onload = () => resolve({ name: f.name, text: String(reader.result) });
    reader.onerror = () => reject(new Error("The file couldn't be read."));
    reader.readAsText(f);
  });
}

// --- set it up --------------------------------------------------------------------------------

function showError(text) {
  $("activate-error").textContent = text;
  $("activate-error").hidden = !text;
}

$("file-button").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", async () => {
  try {
    const f = await readFile($("file-input"));
    if (f) {
      fileText = f.text;
      $("file-name").textContent = f.name;
    }
  } catch (e) {
    showError(e.message);
  }
});

$("activate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const companyId = $("company-id").value.trim();
  const activationKey = $("activation-key").value.trim();
  if (!companyId) return showError("Enter the Company ID.");
  if (!activationKey) return showError("Enter the activation key.");
  if (!fileText) return showError("Choose the license file.");
  showError("");
  $("activate-button").disabled = true;
  $("activate-button").textContent = "Checking…";
  const result = await window.nabhi.activate({ companyId, activationKey, fileText });
  $("activate-button").disabled = false;
  $("activate-button").textContent = "Set up";
  if (!result.ok) showError(result.error);
});

if (view === "activate") $("company-id").focus();

// --- what's wrong -----------------------------------------------------------------------------

$("problem-company").textContent = asked.get("company") ?? "";
$("problem-text").textContent = asked.get("error") ?? "";
$("retry").addEventListener("click", () => window.nabhi.retry());
$("remove").addEventListener("click", () => window.nabhi.remove());
$("renew-button").addEventListener("click", () => $("renew-input").click());
$("renew-input").addEventListener("change", async () => {
  try {
    const f = await readFile($("renew-input"));
    if (!f) return;
    const result = await window.nabhi.renew(f.text);
    if (!result.ok) $("problem-text").textContent = result.error;
  } catch (e) {
    $("problem-text").textContent = e.message;
  }
});
