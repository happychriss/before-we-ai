// The run page: one POST per step, in order. Everything else is plain links
// and forms — the server re-derives every status on each page load.
(function () {
  const next = document.getElementById("run-next");
  const all = document.getElementById("run-all");
  if (!next && !all) return;
  const error = document.getElementById("run-error");

  async function step(key) {
    const row = document.querySelector(`.step[data-key="${key}"]`);
    row.classList.remove("next");
    row.classList.add("running");
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    const response = await fetch(`/api/run/${key}`, { method: "POST" });
    const body = await response.json();
    row.classList.remove("running");
    if (!body.ok) {
      error.textContent = `Step '${key}' failed: ${body.error}`;
      error.hidden = false;
      return null;
    }
    row.classList.add("done");
    row.querySelector(".step-summary").textContent = body.summary;
    return body.next;
  }

  async function run(untilEnd) {
    next.disabled = all.disabled = true;
    let key = all.dataset.next;
    while (key) {
      const upcoming = await step(key);
      if (upcoming === null) break;
      key = upcoming;
      if (!untilEnd) break;
    }
    window.location.href = key === "" ? "/" : "/run";
  }

  next.addEventListener("click", () => run(false));
  all.addEventListener("click", () => run(true));
})();
