/* Meeting detail page logic. */
const $ = id => document.getElementById(id);
const SB = { scheduled: "primary", completed: "success", archived: "secondary" };
let M = null, PEOPLE = [];

async function load() {
  M = await api("GET", `/api/meetings/${MEETING_ID}`);
  document.title = M.title + " · HandOff";
  renderHeader(); renderOverview(); renderDecisions(); renderItems();
  if (document.activeElement !== $("raw-notes")) $("raw-notes").value = M.raw_notes || "";
  if (typeof onMeetingLoaded === "function") onMeetingLoaded(M);
}

function renderHeader() {
  const done = M.status === "completed", sched = M.status === "scheduled";
  $("header").innerHTML = `
    <div class="d-flex flex-wrap justify-content-between align-items-start gap-2">
      <div><h1 class="h3 mb-1">${esc(M.title)}</h1>
        <span class="badge text-bg-${SB[M.status]}">${M.status}</span>
        <span class="badge text-bg-light border">${M.type}</span>
        <span class="text-muted ms-2">${fmtDate(M.date)}</span>
        ${M.previous_meeting ? `<span class="ms-2 small">Carried from <a href="/meetings/${M.previous_meeting.id}">${esc(M.previous_meeting.title)}</a></span>` : ""}</div>
      <div class="d-flex gap-2">
        ${sched ? `<button class="btn btn-success" onclick="setStatus('completed')"><i class="bi bi-check2-circle"></i> Mark completed</button>` : ""}
        ${done ? `<button class="btn btn-dark" onclick="openNext()"><i class="bi bi-arrow-right-circle"></i> Create next meeting</button>` : ""}
        ${M.status !== "archived" ? `<button class="btn btn-outline-secondary" onclick="setStatus('archived')"><i class="bi bi-archive"></i> Archive</button>` : ""}
      </div>
    </div>`;
}

function renderOverview() {
  const agenda = M.agenda.length ? `<ol class="mb-0">${M.agenda.map(a => `<li>${esc(a)}</li>`).join("")}</ol>` : `<span class="text-muted">No agenda.</span>`;
  const parts = M.participants.map(p => `<div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" ${p.attended ? "checked" : ""} onchange="setAttended('${p.person_id}', this.checked)" id="att-${p.person_id}">
    <label class="form-check-label" for="att-${p.person_id}">${esc(p.name)} <span class="text-muted small">${p.attended ? "attended" : "not marked"}</span></label></div>`).join("");
  $("t-overview").innerHTML = `<div class="row g-3">
    <div class="col-md-6"><div class="card border-0 shadow-sm h-100"><div class="card-body"><h2 class="h6">Agenda</h2>${agenda}</div></div></div>
    <div class="col-md-6"><div class="card border-0 shadow-sm h-100"><div class="card-body"><h2 class="h6">Participants</h2>${parts || '<span class="text-muted">No participants.</span>'}</div></div></div>
    ${M.summary ? `<div class="col-12"><div class="card border-0 shadow-sm"><div class="card-body"><h2 class="h6">Summary ${M.recap_source ? `<span class="badge text-bg-light border">${M.recap_source}</span>` : ""}</h2><p class="mb-0">${esc(M.summary)}</p></div></div></div>` : ""}
  </div>`;
}

function renderDecisions() {
  const rows = M.decisions.map((d, i) => `<li class="list-group-item d-flex justify-content-between"><span>${esc(d.text)} ${d.made_by ? `<span class="text-muted small">— ${esc(d.made_by)}</span>` : ""}</span>
    <button class="btn btn-sm btn-link text-danger" onclick="delDecision(${i})"><i class="bi bi-trash"></i></button></li>`).join("");
  $("t-decisions").innerHTML = `<div class="card border-0 shadow-sm"><div class="card-body">
    <ul class="list-group list-group-flush mb-3">${rows || '<li class="list-group-item text-muted">No decisions recorded yet.</li>'}</ul>
    <form class="d-flex gap-2" onsubmit="addDecision(event)"><input class="form-control" id="dec-text" placeholder="Add a decision…" minlength="3" required>
      <button class="btn btn-dark">Add</button></form></div></div>`;
}

function renderItems() {
  $("item-count").textContent = M.items.length;
  $("item-rows").innerHTML = M.items.length ? M.items.map(i => ItemUI.row(i)).join("")
    : `<tr><td colspan="6"><div class="empty-state"><i class="bi bi-list-check fs-2"></i><div>No action items yet.</div></div></td></tr>`;
}

async function patchMeeting(body, msg) { try { await api("PATCH", `/api/meetings/${MEETING_ID}`, body); if (msg) toast(msg); await load(); } catch (_) {} }
const setAttended = (pid, v) => patchMeeting({ attendance: { [pid]: v } });
const addDecision = e => { e.preventDefault(); patchMeeting({ decisions: [...M.decisions, { text: $("dec-text").value }] }, "Decision added"); };
const delDecision = i => patchMeeting({ decisions: M.decisions.filter((_, k) => k !== i) }, "Decision removed");
async function setStatus(s) { try { await api("POST", `/api/meetings/${MEETING_ID}/status`, { status: s }); toast("Meeting " + s); await load(); } catch (_) {} }

function openNext() {
  $("nx-title").value = M.title.replace(/\d+/, n => +n + 1);
  $("nx-date").value = new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10);
  new bootstrap.Modal("#nextModal").show();
}
$("nextForm").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const n = await api("POST", `/api/meetings/${MEETING_ID}/next`, { title: $("nx-title").value, date: $("nx-date").value });
    toast(`Created. ${n.carried_count} open item(s) carried forward.`); location.href = "/meetings/" + n.id;
  } catch (_) {}
});
$("addItemForm").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api("POST", "/api/items", { title: $("ai-title").value, description: $("ai-desc").value, owner_id: $("ai-owner").value || null,
      due_date: $("ai-due").value || null, priority: $("ai-prio").value, meeting_id: MEETING_ID });
    bootstrap.Modal.getInstance($("addItem")).hide(); e.target.reset(); toast("Action item added"); await load();
  } catch (_) {}
});
$("save-notes").addEventListener("click", () => patchMeeting({ raw_notes: $("raw-notes").value }, "Notes saved"));

(async () => {
  PEOPLE = await loadPeople();
  $("ai-owner").innerHTML = personOptions(PEOPLE, "");
  ItemUI.init(PEOPLE, load);
  await load();
})();
