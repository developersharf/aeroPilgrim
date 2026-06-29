/* UmrahFly Dashboard — SPA behavior
 * All network calls use fetch + JSON. No full page reloads.
 */
(function () {
    "use strict";

    function getCsrf() {
        const c = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return c ? c[1] : "";
    }

    function getAttr(name, template) {
        const root = document.querySelector(".page-shell");
        if (!root) return null;
        const v = root.getAttribute(name);
        if (!v) return null;
        return template ? template.replace("0", v) : v;
    }

    function showToast(msg, type) {
        const c = document.getElementById("messagesContainer") || (() => {
            const d = document.createElement("div");
            d.id = "messagesContainer";
            d.className = "fixed top-20 right-4 z-50 space-y-2 max-w-sm";
            document.body.appendChild(d);
            return d;
        })();
        const colors = {
            success: "border-green-500/40 bg-green-500/10",
            error: "border-red-500/40 bg-red-500/10",
            warning: "border-yellow-500/40 bg-yellow-500/10",
            info: "border-blue-500/40 bg-blue-500/10",
        };
        const icons = {
            success: "ph-check-circle text-green-400",
            error: "ph-warning-circle text-red-400",
            warning: "ph-warning text-yellow-400",
            info: "ph-info text-blue-400",
        };
        const el = document.createElement("div");
        el.className = "site-alert flex items-center gap-3 px-4 py-3 rounded-lg text-sm shadow-lg border " + (colors[type || "info"]);
        el.innerHTML = '<i class="ph ' + (icons[type || "info"]) + '"></i><span>' + msg + "</span>";
        c.appendChild(el);
        setTimeout(() => el.remove(), 5000);
    }

    function formatMoney(n) {
        if (n == null) return "—";
        return "$" + Number(n).toFixed(0);
    }

    function fmtDate(d) {
        if (!d) return "";
        const dt = new Date(d);
        if (isNaN(dt)) return d;
        return dt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    }

    /* ------- QUOTA ------- */
    function updateQuota(used, total) {
        const u = document.getElementById("quotaUsed");
        const b = document.getElementById("quotaBar");
        if (u) u.textContent = String(used);
        if (b) b.style.width = (total ? (used / total) * 100 : 0) + "%";
    }

    /* ------- SEARCH ------- */
    function renderResults(payload, sourceLabel) {
        const sec = document.getElementById("searchResultsSection");
        const title = document.getElementById("searchResultsTitle");
        const meta = document.getElementById("searchResultsMeta");
        const body = document.getElementById("searchResultsBody");
        sec.classList.remove("hidden");
        title.textContent = sourceLabel || "Results";

        const cheapest = payload.cheapest || null;
        const all = payload.results || [];
        const cache = payload.cache ? "cached" : "fresh";
        const quota = payload.quota_used + "/" + payload.quota_total;
        meta.textContent = `${cache} · quota ${quota} · ${all.length} days`;

        let html = "";
        if (cheapest) {
            const fd = (getAttr("data-flight-detail-url-template") || "").replace("0", cheapest.search_id).replace("YYYY-MM-DD", cheapest.date);
            html += `
                <div class="glass-sm rounded-lg p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                    <div class="flex-1">
                        <div class="text-xs text-muted">Cheapest match</div>
                        <div class="text-xl font-700">${formatMoney(cheapest.price)}</div>
                        <div class="text-sm">${fmtDate(cheapest.date)} · ${cheapest.stay} day stay · ${cheapest.origin} → ${cheapest.destination}</div>
                    </div>
                    <a href="${fd}" class="apple-btn apple-btn--sm">
                        <i class="ph ph-arrow-right"></i> View trip
                    </a>
                </div>`;
        } else {
            html = `<p class="text-sm text-muted">No matches found in the search window.</p>`;
        }
        html += `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">`;
        all.slice(0, 24).forEach((r) => {
            const fd = (getAttr("data-flight-detail-url-template") || "").replace("0", r.search_id).replace("YYYY-MM-DD", r.date);
            html += `
                <a href="${fd}" class="glass-sm rounded-md p-3 flex justify-between items-center hover:bg-white/10 transition-colors">
                    <div>
                        <div class="text-sm font-600">${fmtDate(r.date)}</div>
                        <div class="text-xs text-muted">${r.stay || 0}d stay</div>
                    </div>
                    <div class="font-mono text-sm">${formatMoney(r.price)}</div>
                </a>`;
        });
        html += "</div>";
        body.innerHTML = html;
    }

    function renderLoading(jobId) {
        const sec = document.getElementById("searchResultsSection");
        const title = document.getElementById("searchResultsTitle");
        const meta = document.getElementById("searchResultsMeta");
        const body = document.getElementById("searchResultsBody");
        sec.classList.remove("hidden");
        title.textContent = "Searching…";
        meta.textContent = "job " + jobId;
        body.innerHTML = `
            <div class="flex items-center gap-3 p-4 glass-sm rounded-lg">
                <div class="animate-spin w-5 h-5 border-2 border-primary-400 border-t-transparent rounded-full"></div>
                <div>
                    <div class="text-sm font-600">Searching in the background</div>
                    <div class="text-xs text-muted">This usually takes a few seconds. Feel free to keep browsing.</div>
                </div>
            </div>`;
    }

    function pollJob(jobId, tries) {
        tries = tries || 0;
        const tmpl = getAttr("data-search-status-url-template");
        const url = (tmpl || "").replace("0", jobId);
        fetch(url, { credentials: "same-origin" })
            .then((r) => r.json())
            .then((data) => {
                if (data.status === "completed" && data.result) {
                    renderResults(data.result, "Background results");
                } else if (data.status === "failed") {
                    showToast(data.error || "Search failed.", "error");
                } else if (tries < 60) {
                    setTimeout(() => pollJob(jobId, tries + 1), 1500);
                } else {
                    showToast("Search timed out.", "warning");
                }
            })
            .catch(() => {
                if (tries < 60) setTimeout(() => pollJob(jobId, tries + 1), 2000);
            });
    }

    function handleSearch(ev) {
        ev.preventDefault();
        const form = ev.target;
        const fd = new FormData(form);
        const params = new URLSearchParams();
        for (const [k, v] of fd.entries()) {
            if (v !== "" && v != null) params.append(k, v);
        }
        const isAsync = fd.get("async_mode") === "on";

        const sec = document.getElementById("searchResultsSection");
        sec.classList.remove("hidden");
        document.getElementById("searchResultsBody").innerHTML =
            `<div class="flex items-center gap-2 text-sm text-muted"><div class="animate-spin w-4 h-4 border-2 border-primary-400 border-t-transparent rounded-full"></div> Submitting…</div>`;

        const url = (isAsync ? getAttr("data-search-async-url") : getAttr("data-search-url")) + "?" + params.toString();

        fetch(url, {
            method: "GET",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then((r) => r.json().then((j) => ({ status: r.status, body: j })))
            .then(({ status, body }) => {
                if (body.quota_exceeded) {
                    updateQuota(body.quota_used || 0, body.quota_total || 1);
                    document.getElementById("searchResultsBody").innerHTML =
                        `<div class="p-4 glass-sm rounded-lg border border-yellow-500/30">
                            <div class="font-600 mb-1">Daily quota reached</div>
                            <div class="text-sm text-muted mb-3">${body.error || ""}</div>
                            <a href="${getAttr("data-pricing-url") || "#"}" class="apple-btn apple-btn--sm"><i class="ph ph-crown"></i> Upgrade</a>
                        </div>`;
                    showToast("Quota exceeded.", "warning");
                    return;
                }
                if (body.job_id) {
                    renderLoading(body.job_id);
                    pollJob(body.job_id, 0);
                    return;
                }
                if (status >= 400) {
                    showToast(body.error || "Search failed.", "error");
                    return;
                }
                if (body.quota_used != null) updateQuota(body.quota_used, body.quota_total);
                renderResults(body, "Results");
                loadHistory();
            })
            .catch((e) => showToast("Network error: " + e.message, "error"));
    }

    /* ------- HISTORY ------- */
    function loadHistory() {
        const list = document.getElementById("historyList");
        list.innerHTML = `<div class="empty">Loading…</div>`;
        fetch(getAttr("data-history-url"), { credentials: "same-origin", headers: { Accept: "application/json" } })
            .then((r) => r.json())
            .then((items) => {
                if (!items.length) {
                    list.innerHTML = `<div class="empty">No searches yet. Run one above to see history here.</div>`;
                    return;
                }
                list.innerHTML = "";
                items.forEach((h) => {
                    const fd = (getAttr("data-flight-detail-url-template") || "").replace("0", h.search_id).replace("YYYY-MM-DD", h.date);
                    const el = document.createElement("div");
                    el.className = "glass-sm rounded-md p-3 flex flex-col sm:flex-row sm:items-center gap-2";
                    el.innerHTML = `
                        <div class="flex-1">
                            <div class="text-sm font-600">${h.city_departure} → ${h.city_arrival}</div>
                            <div class="text-xs text-muted">${fmtDate(h.date_departure)} · ${h.days || 0}d stay · ${h.flex_days || 0}± flex</div>
                        </div>
                        <div class="text-xs font-mono text-muted">${fmtDate(h.created_at)}</div>
                        <div class="flex items-center gap-2">
                            <a href="${fd}" class="apple-btn apple-btn--sm"><i class="ph ph-arrow-right"></i> Open</a>
                            <button data-rerun="${h.id}" class="btn-white btn-white--sm"><i class="ph ph-arrows-clockwise"></i> Rerun</button>
                        </div>`;
                    list.appendChild(el);
                });
                list.querySelectorAll("[data-rerun]").forEach((btn) => {
                    btn.addEventListener("click", () => rerunHistory(parseInt(btn.getAttribute("data-rerun"), 10)));
                });
            })
            .catch(() => {
                list.innerHTML = `<div class="empty">Could not load history.</div>`;
            });
    }

    function rerunHistory(historyId) {
        const url = (getAttr("data-history-rerun-url-template") || "").replace("0", historyId);
        fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
            .then((r) => r.json())
            .then((body) => {
                if (body.quota_exceeded) {
                    showToast("Quota exceeded.", "warning");
                    updateQuota(body.quota_used || 0, body.quota_total || 1);
                    return;
                }
                if (body.job_id) {
                    renderLoading(body.job_id);
                    pollJob(body.job_id, 0);
                } else if (body.cheapest || body.results) {
                    if (body.quota_used != null) updateQuota(body.quota_used, body.quota_total);
                    renderResults(body, "Re-run results");
                } else {
                    showToast(body.error || "Re-run failed.", "error");
                }
            })
            .catch((e) => showToast("Network error: " + e.message, "error"));
    }

    /* ------- WATCHLISTS ------- */
    function loadWatchlists() {
        const list = document.getElementById("watchlistList");
        list.innerHTML = `<div class="empty">Loading…</div>`;
        fetch(getAttr("data-watchlist-url"), { credentials: "same-origin", headers: { Accept: "application/json" } })
            .then((r) => r.json())
            .then((items) => {
                if (!items.length) {
                    list.innerHTML = `<div class="empty">No watchlists yet. Create one to track price changes.</div>`;
                    return;
                }
                list.innerHTML = "";
                items.forEach((w) => {
                    const el = document.createElement("div");
                    el.className = "glass-sm rounded-md p-3 flex flex-col sm:flex-row sm:items-center gap-2";
                    el.innerHTML = `
                        <div class="flex-1">
                            <div class="text-sm font-600" data-name="${w.id}">${w.name}</div>
                            <div class="text-xs text-muted">${w.city_departure} → ${w.city_arrival}</div>
                        </div>
                        <div class="flex items-center gap-2">
                            <button data-edit="${w.id}" class="btn-white btn-white--sm"><i class="ph ph-pencil"></i></button>
                            <button data-del="${w.id}" class="btn-white btn-white--sm"><i class="ph ph-trash"></i></button>
                        </div>`;
                    list.appendChild(el);
                });
                list.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => deleteWatch(parseInt(b.getAttribute("data-del"), 10))));
                list.querySelectorAll("[data-edit]").forEach((b) =>
                    b.addEventListener("click", () => {
                        const id = parseInt(b.getAttribute("data-edit"), 10);
                        const w = items.find((x) => x.id === id);
                        if (!w) return;
                        const newName = prompt("New name", w.name);
                        if (newName && newName !== w.name) updateWatch(id, { name: newName });
                    })
                );
            });
    }

    function createWatch(form) {
        const fd = new FormData(form);
        const body = JSON.stringify({
            name: fd.get("name"),
            city_departure: fd.get("city_departure"),
            city_arrival: fd.get("city_arrival"),
        });
        fetch(getAttr("data-watchlist-create-url"), {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf(), Accept: "application/json" },
            body,
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.id) {
                    form.reset();
                    form.classList.add("hidden");
                    showToast("Watchlist created.", "success");
                    loadWatchlists();
                } else {
                    showToast(data.error || "Could not create.", "error");
                }
            });
    }

    function updateWatch(id, patch) {
        const url = (getAttr("data-watchlist-update-url-template") || "").replace("0", id);
        fetch(url, {
            method: "PATCH",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf(), Accept: "application/json" },
            body: JSON.stringify(patch),
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.id) {
                    showToast("Updated.", "success");
                    loadWatchlists();
                } else {
                    showToast(data.error || "Update failed.", "error");
                }
            });
    }

    function deleteWatch(id) {
        if (!confirm("Delete this watchlist?")) return;
        const url = (getAttr("data-watchlist-delete-url-template") || "").replace("0", id);
        fetch(url, {
            method: "DELETE",
            credentials: "same-origin",
            headers: { "X-CSRFToken": getCsrf(), Accept: "application/json" },
        })
            .then((r) => r.json())
            .then((data) => {
                if (data.ok) {
                    showToast("Deleted.", "success");
                    loadWatchlists();
                } else {
                    showToast(data.error || "Delete failed.", "error");
                }
            });
    }

    /* ------- BOOTSTRAP ------- */
    document.addEventListener("DOMContentLoaded", function () {
        const searchForm = document.getElementById("searchForm");
        if (searchForm) searchForm.addEventListener("submit", handleSearch);

        const refresh = document.getElementById("refreshHistory");
        if (refresh) refresh.addEventListener("click", loadHistory);

        const toggle = document.getElementById("toggleWatchForm");
        const wform = document.getElementById("watchForm");
        if (toggle && wform) toggle.addEventListener("click", () => wform.classList.toggle("hidden"));
        if (wform) wform.addEventListener("submit", (e) => { e.preventDefault(); createWatch(wform); });

        loadHistory();
        loadWatchlists();
    });
})();