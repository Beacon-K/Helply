// Cloud servers list: sparklines, instant search / filters / layout, and in-place live updates.
// Numbers update where they are (no flicker); when a server is added, removed or changes state
// the page body is re-rendered from the server so everything stays consistent.
(function () {
  "use strict";
  const POLL_MS = 5000;
  const VIEW_KEY = "helply.fleet.view";
  let root = document.getElementById("fx-root");
  if (!root) return;

  const fmt = {
    pct: (v) => (v == null ? "–" : Math.round(v).toString()),
    load: (v) => (v == null ? "–" : Number(v).toFixed(2)),
    rate(v) {
      if (v == null) return "–";
      const units = ["B/s", "KB/s", "MB/s", "GB/s"];
      let i = 0;
      while (Math.abs(v) >= 1024 && i < units.length - 1) { v /= 1024; i++; }
      return i === 0 ? `${Math.round(v)} ${units[i]}` : `${v.toFixed(1)} ${units[i]}`;
    },
    uptime(s) {
      if (s == null) return "–";
      const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
      return d ? `${d}d ${h}h` : `${h}h ${m}m`;
    },
  };
  const level = (v) => (v == null ? "none" : v >= 85 ? "hot" : v >= 70 ? "warm" : "ok");
  const readJSON = (id) => { try { return JSON.parse(document.getElementById(id).textContent); } catch (e) { return null; } };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };

  // ---- sparklines -----------------------------------------------------------------------------
  let gradientSeq = 0;
  function drawSpark(svg, values) {
    const vb = svg.viewBox.baseVal;
    const w = vb.width, h = vb.height, pad = 3;
    const points = (values || []).map((v, i) => [i, v]).filter((p) => p[1] != null);
    svg.innerHTML = "";
    if (points.length < 2) return;
    const n = Math.max(values.length - 1, 1);
    // scale to the data (at least 0-20%) so quiet servers still show their shape; the number shows the value
    const peak = Math.max(...points.map((p) => p[1]));
    const top = Math.min(100, Math.max(20, Math.ceil((peak * 1.35) / 10) * 10));
    const x = (i) => (i / n) * w;
    const y = (v) => pad + (h - pad * 2) * (1 - Math.min(Math.max(v, 0), top) / top);
    // break the line where readings are missing
    let d = "", area = "", run = [];
    const flush = () => {
      if (run.length > 1) {
        const seg = run.map((p, j) => `${j ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
        d += seg;
        area += `${seg}L${x(run[run.length - 1][0]).toFixed(1)},${h}L${x(run[0][0]).toFixed(1)},${h}Z`;
      }
      run = [];
    };
    // bridge up to 3 empty buckets (a missed report or two); longer gaps really mean no data
    let missing = 0;
    values.forEach((v, i) => {
      if (v == null) { if (++missing > 3) flush(); return; }
      missing = 0;
      run.push([i, v]);
    });
    flush();
    const id = `fxg${++gradientSeq}`;
    const ns = "http://www.w3.org/2000/svg";
    const mini = vb.width < 100;
    svg.insertAdjacentHTML("beforeend",
      `<defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity="${mini ? 0.12 : 0.18}"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>` +
      `<path class="area" d="${area}" fill="url(#${id})"/><path class="line" d="${d}"/>`);
    const last = points[points.length - 1];
    if (!mini) {
      const tip = document.createElementNS(ns, "circle");
      tip.setAttribute("class", "tip");
      tip.setAttribute("cx", x(last[0]));
      tip.setAttribute("cy", y(last[1]));
      tip.setAttribute("r", 3);
      svg.appendChild(tip);
    }
  }

  function sparkColour(svg, state) {
    svg.style.color = state === "warning" ? "#f79009" : state === "offline" ? "#98a2b3" : "#12b76a";
    svg.querySelectorAll(".line, .tip").forEach((el) => (el.style.stroke = svg.style.color));
  }

  function paintSparks(data) {
    (data.servers || []).forEach((srv) => {
      root.querySelectorAll(`[data-server="${srv.id}"] svg[data-spark]`).forEach((svg) => {
        drawSpark(svg, srv.spark);
        sparkColour(svg, srv.state);
      });
    });
  }

  // ---- filters, search, layout --------------------------------------------------------------
  const state = { filter: "all", q: "", view: store.get(VIEW_KEY) || "grid" };

  function applyFilters() {
    const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;
    root.querySelectorAll(".fx-grid [data-server], .fx-table tbody tr").forEach((el) => {
      const s = el.dataset.state;
      const okState = state.filter === "all" || s === state.filter || (state.filter === "offline" && s === "pending");
      const hay = (el.dataset.search || "").toLowerCase();
      const okText = words.every((w) => hay.includes(w));
      el.classList.toggle("fx-hidden", !(okState && okText));
      if (okState && okText && el.closest(".fx-grid")) shown++;
    });
    const none = root.querySelector("[data-fx-noresult]");
    if (none) none.classList.toggle("fx-hidden", shown > 0 || !root.querySelector(".fx-grid"));
    root.querySelectorAll("[data-fx-filter]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.fxFilter === state.filter)));
    root.dataset.view = state.view;
    root.querySelectorAll("[data-fx-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.fxView === state.view)));
  }

  function bind() {
    const search = root.querySelector("[data-fx-search]");
    if (search) {
      search.value = state.q;
      search.addEventListener("input", () => { state.q = search.value; applyFilters(); });
      search.addEventListener("keydown", (e) => { if (e.key === "Escape") { search.value = ""; state.q = ""; applyFilters(); } });
    }
    root.querySelectorAll("[data-fx-filter]").forEach((b) => b.addEventListener("click", () => { state.filter = b.dataset.fxFilter; applyFilters(); }));
    root.querySelectorAll("[data-fx-view]").forEach((b) => b.addEventListener("click", () => {
      state.view = b.dataset.fxView; store.set(VIEW_KEY, state.view); applyFilters();
    }));
    const reset = root.querySelector("[data-fx-reset]");
    if (reset) reset.addEventListener("click", () => { state.q = ""; state.filter = "all"; if (search) search.value = ""; applyFilters(); });
    root.querySelectorAll(".fx-table tbody tr[data-href]").forEach((tr) => tr.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      window.location.href = tr.dataset.href;
    }));
  }

  // "/" focuses search, like most developer tools
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.target.closest("input, textarea, select")) return;
    const s = root.querySelector("[data-fx-search]");
    if (s) { e.preventDefault(); s.focus(); }
  });

  // ---- live updates -------------------------------------------------------------------------
  let lastOk = Date.now();
  let failing = false;

  function setText(el, text) {
    if (el.textContent === text) return;
    el.textContent = text;
    el.classList.remove("fx-flash");
    void el.offsetWidth; // restart the animation
    el.classList.add("fx-flash");
  }

  function updateInPlace(data) {
    data.servers.forEach((srv) => {
      root.querySelectorAll(`[data-server="${srv.id}"]`).forEach((box) => {
        const online = srv.status === "online";
        box.querySelectorAll("[data-k]").forEach((el) => {
          const key = el.dataset.k;
          let value = key === "load1" ? srv.load[0] : srv[key];
          if (!online && ["cpu", "rx", "uptime"].includes(key)) value = null;
          const kind = el.dataset.fmt || "pct";
          setText(el, fmt[kind](value));
        });
        box.querySelectorAll("[data-bar]").forEach((bar) => {
          const v = srv[bar.dataset.bar];
          bar.style.width = `${v == null ? 0 : Math.min(v, 100)}%`;
          bar.className = `lv-${level(v)}`;
        });
      });
    });
    const avg = root.querySelector('[data-fx-sum="avg_cpu"]');
    if (avg) setText(avg, fmt.pct(data.summary.avg_cpu));
    paintSparks(data);
  }

  async function rerender() {
    const response = await fetch(window.location.href, { credentials: "same-origin" });
    if (!response.ok || response.redirected) throw new Error("reload failed");
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    const fresh = doc.getElementById("fx-root");
    const json = doc.getElementById("fx-fleet");
    if (!fresh) throw new Error("no content");
    const known = new Set([...root.querySelectorAll(".fx-grid [data-server]")].map((el) => el.dataset.server));
    root.replaceWith(fresh);
    root = fresh;
    if (json) document.getElementById("fx-fleet").textContent = json.textContent;
    root.querySelectorAll(".fx-grid [data-server]").forEach((el) => { if (!known.has(el.dataset.server)) el.classList.add("is-entering"); });
    bind();
    applyFilters();
    paintSparks(readJSON("fx-fleet") || { servers: [] });
  }

  async function poll() {
    if (document.hidden) return;
    try {
      const response = await fetch(root.dataset.url, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (response.redirected || response.status === 403) { failing = true; tick("Signed out - reload the page"); return; }
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      if (data.signature !== root.dataset.signature) await rerender();
      else updateInPlace(data);
      lastOk = Date.now();
      failing = false;
    } catch (e) {
      failing = true;
    }
    tick();
  }

  function tick(message) {
    const el = root.querySelector("[data-fx-updated]");
    if (!el) return;
    if (message) { el.textContent = message; return; }
    const age = Math.round((Date.now() - lastOk) / 1000);
    el.textContent = failing ? "Connection lost - retrying…" : age < 3 ? "updated just now" : `updated ${age}s ago`;
  }

  bind();
  applyFilters();
  paintSparks(readJSON("fx-fleet") || { servers: [] });
  tick();
  if (root.querySelector(".fx-grid") || root.querySelector(".fx-empty")) {
    setInterval(poll, POLL_MS);
    setInterval(() => tick(), 1000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
  }
})();
