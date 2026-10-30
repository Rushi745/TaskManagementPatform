/* Shared item UI: rows, detail offcanvas, close/reopen modals.
   ItemUI.init(people, onChange) once; ItemUI.row(item) renders a <tr>. */
const ItemUI = (() => {
  let people = [], onChange = () => {}, currentId = null, closeModal, reopenModal, canvas;
  const EVENT_ICON = { created: "plus-circle", status_changed: "arrow-repeat", reassigned: "person-lines-fill", carried_forward: "arrow-right-circle", closed: "check-circle", reopened: "arrow-counterclockwise", due_changed: "calendar-event", updated: "pencil" };

  function init(p, cb) {
    people = p; onChange = cb || onChange;
    closeModal = new bootstrap.Modal("#closeModal"); reopenModal = new bootstrap.Modal("#reopenModal");
    canvas = new bootstrap.Offcanvas("#itemCanvas");
    document.getElementById("closeForm").addEventListener("submit", async e => {
      e.preventDefault();
      try {
        await api("POST", `/api/items/${currentId}/close`, { status: val("close-status"), outcome: val("close-outcome") });
        closeModal.hide(); toast("Item closed"); await refresh();
      } catch (_) {}
    });
    document.getElementById("reopenForm").addEventListener("submit", async e => {
      e.preventDefault();
      try {
        await api("POST", `/api/items/${currentId}/reopen`, { note: val("reopen-note") });
        reopenModal.hide(); toast("Item reopened"); await refresh();
      } catch (_) {}
    });
  }
  const val = id => document.getElementById(id).value;

  async function refresh() { await onChange(); if (document.getElementById("itemCanvas").classList.contains("show")) await open(currentId); }

  function dueHtml(i) { return i.due_date ? `<span class="${i.is_overdue ? "overdue" : ""}">${fmtDate(i.due_date)}${i.is_overdue ? " <i class='bi bi-exclamation-circle'></i>" : ""}</span>` : "—"; }
  const PRIO = { high: "danger", medium: "warning text-dark", low: "secondary" };

  function badges(i) {
    return (i.carry_count ? ` <span class="badge text-bg-info" title="Carried across meetings">carried ×${i.carry_count}</span>` : "")
      + ((i.handover_notes || []).length ? ` <span class="badge text-bg-warning" title="Has handover notes"><i class="bi bi-person-walking"></i> handed over</span>` : "")
      + (i.needs_review ? ` <span class="badge text-bg-warning" title="AI was unsure about owner/date">⚠ review</span>` : "");
  }

  function row(i, showMeeting = false) {
    const closed = ["done", "dropped"].includes(i.status);
    const statusCell = closed ? statusBadge(i.status) :
      `<select class="form-select form-select-sm" style="width:130px" onchange="ItemUI.setStatus('${i.id}', this.value)">
        ${["open", "in_progress", "blocked"].map(s => `<option value="${s}" ${s === i.status ? "selected" : ""}>${s.replace("_", " ")}</option>`).join("")}</select>`;
    return `<tr>
      <td><a href="#" class="text-decoration-none fw-semibold" onclick="ItemUI.open('${i.id}');return false">${esc(i.title)}</a>${badges(i)}</td>
      <td>${esc(i.owner_name || "Unassigned")}</td>
      <td>${dueHtml(i)}</td>
      <td><span class="badge text-bg-${PRIO[i.priority]}">${i.priority}</span></td>
      <td>${statusCell}</td>
      ${showMeeting ? `<td class="small text-muted">${esc(i.origin_meeting_title)}</td>` : ""}
      <td class="text-end">${closed ? `<button class="btn btn-sm btn-outline-secondary" onclick="ItemUI.reopen('${i.id}')">Reopen</button>`
        : `<button class="btn btn-sm btn-outline-success" onclick="ItemUI.close('${i.id}', '${esc(i.title).replace(/'/g, "&#39;")}')">Close</button>`}</td>
    </tr>`;
  }

  async function setStatus(id, status) {
    try { await api("PATCH", `/api/items/${id}`, { status }); toast("Status updated"); await onChange(); } catch (_) { await onChange(); }
  }
  function close(id, title) { currentId = id; document.getElementById("close-title").textContent = title; document.getElementById("close-outcome").value = ""; closeModal.show(); }
  function reopen(id) { currentId = id; document.getElementById("reopen-note").value = ""; reopenModal.show(); }

  async function open(id) {
    currentId = id;
    const i = await api("GET", `/api/items/${id}`);
    const closed = ["done", "dropped"].includes(i.status);
    document.getElementById("ic-title").textContent = i.title;
    const hist = i.history.slice().reverse().map(h => `<div class="timeline-item">
      <div class="small"><i class="bi bi-${EVENT_ICON[h.event] || "dot"} me-1"></i><strong>${h.event.replace("_", " ")}</strong>
        ${h.from != null || h.to != null ? ` <span class="text-muted">${esc(String(h.from ?? "—"))} → ${esc(String(h.to ?? "—"))}</span>` : ""}</div>
      ${h.note ? `<div class="small">${esc(h.note)}</div>` : ""}
      <div class="text-muted" style="font-size:.75rem">${new Date(h.at).toLocaleString()} · ${esc(h.by)}</div></div>`).join("");
    const kb = (i.kb_links || []).map(l => `<li><a href="/kb/${l.doc_id}">${esc(l.title)}</a> <span class="badge text-bg-light">${l.method === "ai" ? "AI" : "keyword match"}</span><div class="small text-muted">${esc(l.reason)}</div></li>`).join("");
    document.getElementById("ic-body").innerHTML = `
      <div class="mb-3">${statusBadge(i.status)} <span class="badge text-bg-${PRIO[i.priority]}">${i.priority}</span>${badges(i)}</div>
      ${i.description ? `<p>${esc(i.description)}</p>` : ""}
      ${i.evidence ? `<blockquote class="small text-muted border-start ps-2">“${esc(i.evidence)}”</blockquote>` : ""}
      ${closed ? `<div class="alert alert-${i.status === "done" ? "success" : "secondary"} py-2"><strong>Outcome:</strong> ${esc(i.outcome)}</div>` : ""}
      <div class="row g-2 mb-3">
        <div class="col-6"><label class="form-label small mb-0">Owner</label>
          <select class="form-select form-select-sm" ${closed ? "disabled" : ""} onchange="ItemUI.reassign('${i.id}', this.value)">${personOptions(people, i.owner_id ? String(i.owner_id) : "")}</select></div>
        <div class="col-6"><label class="form-label small mb-0">Due</label>
          <input type="date" class="form-control form-control-sm" ${closed ? "disabled" : ""} value="${i.due_date ? i.due_date.slice(0, 10) : ""}" onchange="ItemUI.setDue('${i.id}', this.value)"></div>
      </div>
      ${(i.handover_notes || []).slice().reverse().map(h => `<div class="alert alert-warning py-2 small"><strong><i class="bi bi-person-walking"></i> Handed over by ${esc(h.from_name)} → ${esc(h.to_name)}</strong> <span class="text-muted">(leave ${esc(h.leave_from)} to ${esc(h.leave_to)})</span><div style="white-space:pre-wrap" class="mt-1">${esc(h.context)}</div></div>`).join("")}
      <div class="small text-muted mb-3">Meetings: ${i.meeting_titles.map(esc).join(" → ")}</div>
      <div class="mb-3">${closed ? `<button class="btn btn-sm btn-outline-secondary" onclick="ItemUI.reopen('${i.id}')">Reopen</button>`
        : `<button class="btn btn-sm btn-success" onclick="ItemUI.close('${i.id}', '${esc(i.title).replace(/'/g, "&#39;")}')">Close with outcome</button>`}</div>
      <h6>Related documents <button class="btn btn-sm btn-outline-dark ms-2" onclick="ItemUI.findDocs(this, '${i.id}')"><i class="bi bi-stars"></i> Find related docs</button></h6>
      ${kb ? `<ul class="list-unstyled">${kb}</ul>` : '<div class="small text-muted mb-2">None linked yet.</div>'}
      <h6>History</h6><div class="timeline">${hist}</div>`;
    canvas.show();
  }
  async function reassign(id, owner) {
    try { await api("PATCH", `/api/items/${id}`, { owner_id: owner || null }); toast("Reassigned"); await onChange(); await open(id); } catch (_) {}
  }
  async function setDue(id, d) {
    try { await api("PATCH", `/api/items/${id}`, { due_date: d || null }); toast("Due date updated"); await onChange(); await open(id); } catch (_) {}
  }
  async function findDocs(btn, id) {
    await withSpinner(btn, async () => {
      try { const r = await api("POST", `/api/items/${id}/link`); toast(r.kb_links.length ? `Linked ${r.kb_links.length} document(s)${r.source === "fallback" ? " (keyword match, AI unavailable)" : ""}` : "No relevant documents found"); await open(id); } catch (_) {}
    });
  }
  return { init, row, open, close, reopen, setStatus, reassign, setDue, findDocs };
})();
