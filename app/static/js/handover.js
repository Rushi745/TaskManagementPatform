/* Leave Handover wizard: select -> preview (AI brief + suggestions) -> execute. */
const $ = id => document.getElementById(id);
const URG = { overdue: ["danger", "🔴 Overdue"], during: ["warning text-dark", "🟠 Due by leave end"], after: ["success", "🟢 Later / no date"] };
let PV = null, BRIEF_TEXT = "";

function setStep(n) {
  ["s1", "s2", "s3"].forEach((id, k) => $(id).classList.toggle("d-none", k + 1 !== n));
  document.querySelectorAll("#steps .badge").forEach(b => { const on = +b.dataset.step === n; b.className = "badge " + (on ? "text-bg-dark" : "text-bg-light border"); });
}
function back() { setStep(1); }
const addDays = n => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);

(async () => {
  const people = (await loadPeople()).filter(p => p.status === "active");
  $("person").innerHTML = people.map(p => `<option value="${p.id}">${esc(p.name)} (${esc(p.role || "")})</option>`).join("");
  $("lfrom").value = addDays(2); $("lto").value = addDays(16);
})();

$("f1").addEventListener("submit", async e => {
  e.preventDefault();
  await withSpinner($("previewBtn"), async () => {
    try {
      PV = await api("POST", "/api/handover/preview", { from_person_id: $("person").value, leave_from: $("lfrom").value, leave_to: $("lto").value });
      renderPreview();
    } catch (_) {}
  });
});

function ownerSelect(i) {
  return `<select class="form-select form-select-sm owner" data-item="${i.id}" title="${esc(i.suggestion_reason || "")}">` +
    `<option value="">Choose…</option>` + PV.people.map(p => `<option value="${p.id}" ${p.id === i.suggested_owner_id ? "selected" : ""}>${esc(p.name)}</option>`).join("") + `</select>` +
    (i.suggestion_reason ? `<div class="small text-muted mt-1">${esc(i.suggestion_reason)}</div>` : "");
}

function renderPreview() {
  setStep(2);
  $("banner").innerHTML = PV.source === "fallback" ? `<div class="alert alert-warning py-2">AI unavailable — brief generated without AI (template). Review suggestions carefully.</div>` : "";
  $("overview").textContent = PV.overview;
  $("risks").innerHTML = PV.risks.length ? `<h6 class="text-danger">Risks</h6><ul class="mb-0">${PV.risks.map(r => `<li>${esc(r)}</li>`).join("")}</ul>` : "";
  $("bulk").innerHTML = `<option value="">Choose person…</option>` + PV.people.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
  $("rows").innerHTML = PV.items.length ? PV.items.map(i => `<tr>
    <td><div class="fw-semibold">${esc(i.title)}</div><span class="badge text-bg-${URG[i.urgency][0]}">${URG[i.urgency][1]}</span>
      <span class="badge text-bg-light border">${i.status.replace("_", " ")}</span></td>
    <td>${i.due_date ? fmtDate(i.due_date) : "—"}</td><td class="small">${esc(i.context)}</td><td>${ownerSelect(i)}</td></tr>`).join("")
    : `<tr><td colspan="4"><div class="empty-state"><i class="bi bi-check2-circle fs-2"></i><div>${esc(PV.person.name)} has no open items. Nothing to hand over.</div></div></td></tr>`;
  $("execBtn").disabled = !PV.items.length;
  BRIEF_TEXT = [PV.overview, "", ...PV.items.map(i => `• ${i.title} (${i.urgency}, due ${i.due_date ? i.due_date.slice(0, 10) : "n/a"}): ${i.context}`),
    ...(PV.risks.length ? ["", "Risks:", ...PV.risks.map(r => `- ${r}`)] : [])].join("\n");
}

$("bulkBtn").addEventListener("click", () => {
  if (!$("bulk").value) return toast("Pick a person first", "warning");
  document.querySelectorAll(".owner").forEach(s => s.value = $("bulk").value);
});

$("execBtn").addEventListener("click", async e => {
  const assignments = [...document.querySelectorAll(".owner")].map(s => ({ item_id: s.dataset.item, to_person_id: s.value }));
  if (assignments.some(a => !a.to_person_id)) return toast("Choose a new owner for every item", "danger");
  if (!confirm(`Reassign ${assignments.length} item(s) and mark ${PV.person.name} as on leave?`)) return;
  await withSpinner(e.currentTarget, async () => {
    try {
      const r = await api("POST", "/api/handover/execute", { from_person_id: PV.person.id, leave_from: PV.leave_from, leave_to: PV.leave_to,
        assignments, note: $("note").value, brief: BRIEF_TEXT });
      setStep(3);
      $("doneTitle").textContent = "Handover complete";
      $("doneText").textContent = `${r.reassigned} item(s) reassigned from ${r.person}. They are now marked on leave.`;
      $("doneLink").href = "/meetings/" + r.meeting_id;
    } catch (_) {}
  });
});
$("copyBtn").addEventListener("click", async () => { try { await navigator.clipboard.writeText(BRIEF_TEXT); toast("Brief copied"); } catch (_) { toast("Copy failed", "danger"); } });
