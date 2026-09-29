// Nabhi's own screen: set up this PC, opening, and what went wrong.
const $ = (id) => document.getElementById(id);
const views = ["activate", "starting", "problem"];
let fileText = null;

function show(view) {
  for (const v of views) $(v).hidden = v !== view;
}

function readFile(input) {
  return new Promise((resolve, reject) => {
    const f = input.files?.[0];
    if (!f) return resolve(null);
    if (f.size > 64 * 1024) return reject(new Error("That file is too large to be a Nabhi connection file."));
    const reader = new FileReader();
    reader.onload = () => resolve({ name: f.name, text: String(reader.result) });
    reader.onerror = () => reject(new Error("The file couldn't be read."));
    reader.readAsText(f);
  });
}

// --- set up this PC -------------------------------------------------------------------------
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

function showError(text) {
  $("activate-error").textContent = text;
  $("activate-error").hidden = !text;
}

$("activate-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const companyId = $("company-id").value.trim();
  const activationKey = $("activation-key").value.trim();
  if (!companyId) return showError("Enter the Company ID.");
  if (!activationKey) return showError("Enter the activation key.");
  if (!fileText) return showError("Choose the connection file.");
  showError("");
  $("activate-button").disabled = true;
  $("activate-button").textContent = "Checking…";
  const result = await window.nabhi.activate({ companyId, activationKey, fileText });
  $("activate-button").disabled = false;
  $("activate-button").textContent = "Set up";
  if (!result.ok) showError(result.error);
});

// --- problems -------------------------------------------------------------------------------
$("retry").addEventListener("click", () => window.nabhi.retry());
$("replace-button").addEventListener("click", () => $("replace-input").click());
$("replace-input").addEventListener("change", async () => {
  try {
    const f = await readFile($("replace-input"));
    if (!f) return;
    const result = await window.nabhi.replace(f.text);
    if (!result.ok) $("problem-text").textContent = result.error;
  } catch (e) {
    $("problem-text").textContent = e.message;
  }
});
$("forget").addEventListener("click", () => window.nabhi.forget());

// --- what the app says ------------------------------------------------------------------------
window.nabhi.onState((state) => {
  if (state.view === "activate") {
    show("activate");
    $("company-id").focus();
  }
  if (state.view === "starting") {
    show("starting");
    $("starting-company").textContent = state.company ? `${state.company.companyName} (${state.company.companyId})` : "";
    const list = $("steps");
    list.replaceChildren(
      ...state.steps.map((s, i) => {
        const li = document.createElement("li");
        li.textContent = s;
        li.className = i < state.steps.length - 1 ? "done" : "now";
        return li;
      }),
    );
  }
  if (state.view === "problem") {
    show("problem");
    $("problem-company").textContent = state.company ? `${state.company.companyName} (${state.company.companyId})` : "";
    $("problem-text").textContent = state.error;
  }
});
