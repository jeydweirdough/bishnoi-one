// The starting screen: which app, how far it has got, and what to do if it doesn't come up.
const asked = new URLSearchParams(location.search);
const name = asked.get("name") ?? "Bishnoi One";

document.title = name;
document.getElementById("name").textContent = name;
document.getElementById("run").textContent = asked.get("run") ?? "";

const steps = [...document.querySelectorAll("#steps li")];
const ring = document.getElementById("bar");
const sweep = document.getElementById("sweep");
const LENGTH = 2 * Math.PI * 52;

/** Shows `done` steps finished and the next one under way (main.mjs sends each as it happens). */
function show(done) {
  const n = Math.min(done, steps.length - 1);
  steps.forEach((li, i) => {
    li.className = i < n ? "done" : i === n ? "doing" : "";
  });
  ring.style.strokeDashoffset = String(LENGTH * (1 - n / steps.length));
  // The step under way sweeps inside its own quarter of the ring.
  sweep.style.transform = `rotate(${(360 * n) / steps.length}deg)`;
  document.getElementById("count").textContent = `${n + 1}/${steps.length}`;
  document.getElementById("now").textContent = steps[n].textContent;
}

show(0);
window.bishnoi?.onStep?.(show);

const SLOW_AFTER_MS = 45_000;
setTimeout(() => (document.getElementById("slow").hidden = false), SLOW_AFTER_MS);
