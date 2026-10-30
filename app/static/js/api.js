/* fetch wrapper + toasts. api(method, url, body) -> data, throws on error (and shows a toast). */
function toast(message, type = "success", ref = null) {
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${type} border-0`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body"></div>
    <button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  el.querySelector(".toast-body").textContent = message + (ref ? `  (Ref: ${ref})` : "");
  document.getElementById("toasts").appendChild(el);
  const t = new bootstrap.Toast(el, { delay: type === "danger" ? 7000 : 3500 });
  t.show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}

async function api(method, url, body, opts = {}) {
  const init = { method, headers: { "X-Actor": localStorage.getItem("actor") || "Anonymous" } };
  if (body !== undefined && body !== null) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res;
  try { res = await fetch(url, init); }
  catch (e) { if (!opts.silent) toast("Network error. Check your connection.", "danger"); throw e; }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = data.error || { message: "Request failed", details: [] };
    const fields = (err.details || []).map(d => `${d.field}: ${d.msg}`).join("; ");
    if (!opts.silent) toast(fields ? `${err.message} — ${fields}` : err.message, "danger", err.request_id);
    const e = new Error(err.message); e.info = err; throw e;
  }
  return data;
}

/* Run an async action while disabling a button and showing a spinner. */
async function withSpinner(btn, fn) {
  const html = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Working…';
  try { return await fn(); } finally { btn.disabled = false; btn.innerHTML = html; }
}

function esc(s) { const d = document.createElement("div"); d.textContent = s ?? ""; return d.innerHTML; }
function fmtDate(iso) { return iso ? new Date(iso).toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }) : "—"; }
function statusBadge(s) { return `<span class="badge badge-status-${s}">${s.replace("_", " ")}</span>`; }

async function loadPeople() { return api("GET", "/api/people"); }
function personOptions(people, selected, blank = "Unassigned") {
  return `<option value="">${blank}</option>` + people.map(p => `<option value="${p.id}" ${p.id === selected ? "selected" : ""}>${esc(p.name)}${p.status === "on_leave" ? " (on leave)" : ""}</option>`).join("");
}
