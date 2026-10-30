/* Meeting detail: knowledge links + catch-up brief. Uses globals from meeting.js ($, M, PEOPLE). */
function renderKbLinks() {
  const l = M.kb_links || [];
  $("kb-links").innerHTML = l.length ? `<ul class="list-group list-group-flush">${l.map(x => `<li class="list-group-item">
    <a href="/kb/${x.doc_id}" class="fw-semibold text-decoration-none">${esc(x.title)}</a>
    <span class="badge text-bg-light border">${x.method === "ai" ? "AI" : "keyword match"}</span>
    <div class="small text-muted">${esc(x.reason)}</div></li>`).join("")}</ul>`
    : `<div class="empty-state"><i class="bi bi-link-45deg fs-2"></i><div>No documents linked yet.</div></div>`;
}
function fillBriefPeople() {
  const absent = new Set(M.participants.filter(p => !p.attended).map(p => String(p.person_id)));
  const sorted = [...PEOPLE].sort((a, b) => (absent.has(b.id) - absent.has(a.id)) || a.name.localeCompare(b.name));
  $("brief-person").innerHTML = sorted.map(p => `<option value="${p.id}">${esc(p.name)}${absent.has(p.id) ? " (not marked attended)" : ""}</option>`).join("");
}
function onMeetingLoaded() { renderKbLinks(); if (!$("brief-person").options.length) fillBriefPeople(); }

$("find-docs").addEventListener("click", async e => {
  await withSpinner(e.currentTarget, async () => {
    try {
      const r = await api("POST", `/api/meetings/${MEETING_ID}/link`);
      toast(r.kb_links.length ? `Linked ${r.kb_links.length} document(s)${r.source === "fallback" ? " (keyword match)" : ""}` : "No relevant documents found");
      await load();
    } catch (_) {}
  });
});

$("gen-brief").addEventListener("click", async e => {
  await withSpinner(e.currentTarget, async () => {
    try {
      const r = await api("POST", `/api/meetings/${MEETING_ID}/brief`, { person_id: $("brief-person").value, mode: $("brief-mode").value });
      const c = r.content, ul = a => a.length ? `<ul>${a.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : '<div class="text-muted small mb-2">Nothing.</div>';
      $("brief-out").innerHTML = `<div class="card border-primary"><div class="card-body">
        <div class="d-flex justify-content-between"><h2 class="h5">${esc(c.headline)}</h2>
          ${r.source === "fallback" ? '<span class="badge text-bg-warning align-self-start">Generated without AI</span>' : '<span class="badge text-bg-primary align-self-start">AI brief</span>'}</div>
        <h6>What happened</h6>${ul(c.what_happened)}<h6>Decisions affecting you</h6>${ul(c.decisions_affecting_you)}
        <h6>Your action items</h6>${ul(c.your_action_items)}${c.open_questions.length ? `<h6>Open questions</h6>${ul(c.open_questions)}` : ""}
        ${c.read_next.length ? `<h6>Read next</h6>${ul(c.read_next)}` : ""}</div></div>`;
    } catch (_) {}
  });
});
