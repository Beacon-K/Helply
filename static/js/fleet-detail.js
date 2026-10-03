// Server detail: interactive charts (synced crosshair across all four), range switching without a
// page reload, and live readings every 5 seconds. Pure SVG, no chart library.
(function () {
  "use strict";
  const root = document.getElementById("fx-detail");
  if (!root) return;
  const LATEST_MS = 5000;
  const SERIES_MS = 30000;
  const NS = "http://www.w3.org/2000/svg";
  const thresholds = JSON.parse(root.dataset.thresholds || "{}");

  const fmt = {
    pct: (v) => (v == null ? "–" : `${Math.round(v)}%`),
    num: (v) => (v == null ? "–" : Math.round(v).toString()),
    int: (v) => (v == null ? "–" : Math.round(v).toLocaleString("en-CA")),
    load: (v) => (v == null ? "–" : Number(v).toFixed(2)),
    rate(v) {
      if (v == null) return "–";
      const u = ["B/s", "KB/s", "MB/s", "GB/s"]; let i = 0;
      while (Math.abs(v) >= 1024 && i < u.length - 1) { v /= 1024; i++; }
      return i ? `${v.toFixed(1)} ${u[i]}` : `${Math.round(v)} ${u[i]}`;
    },
    bytes(v) {
      if (v == null) return "–";
      const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0;
      while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
      return i < 2 ? `${Math.round(v)} ${u[i]}` : `${v.toFixed(1)} ${u[i]}`;
    },
    uptime(s) {
      if (s == null) return "–";
      const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
      return d ? `${d}d ${h}h` : `${h}h ${m}m`;
    },
    loadavg: (l) => (l ? l.map((x) => (x == null ? "–" : Number(x).toFixed(2))).join(" · ") : "–"),
  };
  const level = (v) => (v == null ? "none" : v >= 85 ? "hot" : v >= 70 ? "warm" : "ok");

  const CHARTS = {
    cpu: { max: 100, f: fmt.pct, threshold: thresholds.cpu,
           series: [{ key: "cpu", label: "CPU", tip: "CPU", color: "#2e90fa", area: true }, { key: "peak", label: "Hourly peak", tip: "CPU peak", color: "#84caff", dash: true }] },
    mem: { max: 100, f: fmt.pct, threshold: thresholds.mem,
           series: [{ key: "mem", label: "Memory", tip: "Memory", color: "#7a5af8", area: true }, { key: "disk", label: "Disk", tip: "Disk", color: "#f79009" }] },
    net: { f: fmt.rate, series: [{ key: "rx", label: "In", tip: "Network in", color: "#12b76a", area: true }, { key: "tx", label: "Out", tip: "Network out", color: "#9e77ed" }] },
    load: { f: fmt.load, series: [{ key: "load", label: "1 min", tip: "Load (1 min)", color: "#344054", area: true }] },
  };

  let payload;
  try { payload = JSON.parse(document.getElementById("fx-payload").textContent); } catch (e) { return; }
  let data = payload.series;
  let server = payload.server;
  const initialSignature = signature(server);
  let hoverTime = null;

  function signature(s) { return `${s.status}|${s.state}|${s.alerts.length}|${s.maintenance}`; }

  // ---------------------------------------------------------------------------- chart drawing
  function niceMax(v) {
    if (!v || v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }
  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }
  function timeLabel(ms, span) {
    const d = new Date(ms);
    if (span <= 36 * 3600e3) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }
  function fullTime(ms) {
    return new Date(ms).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: data.range === "1h" ? "2-digit" : undefined, hour12: false });
  }
  function medianStep(t) {
    if (t.length < 3) return 60e3;
    const steps = [];
    for (let i = 1; i < t.length; i++) steps.push(t[i] - t[i - 1]);
    steps.sort((a, b) => a - b);
    return steps[Math.floor(steps.length / 2)] || 60e3;
  }
  function nearestIndex(t, time) {
    let lo = 0, hi = t.length - 1;
    if (hi < 0) return -1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (t[mid] < time) lo = mid; else hi = mid; }
    return Math.abs(t[lo] - time) <= Math.abs(t[hi] - time) ? lo : hi;
  }

  const charts = {};
  document.querySelectorAll("[data-chart]").forEach((fig) => {
    charts[fig.dataset.chart] = { fig, canvas: fig.querySelector("[data-canvas]"), legend: fig.querySelector("[data-legend]") };
  });

  function render(name) {
    const c = charts[name], def = CHARTS[name];
    const canvas = c.canvas;
    canvas.innerHTML = "";
    const W = canvas.clientWidth || 400, H = canvas.clientHeight || 170;
    const pad = { l: 40, r: 6, t: 8, b: 20 };
    const t = data.t || [];
    const series = def.series.filter((s) => Array.isArray(data[s.key]) && data[s.key].some((v) => v != null));
    c.series = series;
    if (t.length < 2 || !series.length) {
      const empty = document.createElement("div");
      empty.className = "fx-chart-empty";
      empty.textContent = server.status === "pending" ? "Waiting for the first report" : "No readings in this period";
      canvas.appendChild(empty);
      c.legend.innerHTML = "";
      c.scale = null;
      return;
    }
    const x0 = data.from, x1 = data.to;
    let top = def.max;
    if (!top) top = niceMax(Math.max(...series.flatMap((s) => data[s.key].filter((v) => v != null))) * 1.15);
    const X = (ms) => pad.l + ((ms - x0) / (x1 - x0)) * (W - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - Math.min(Math.max(v, 0), top) / top) * (H - pad.t - pad.b);
    c.scale = { X, Y, W, H, pad, top };

    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${name} chart` }, canvas);
    const defs = el("defs", {}, svg);
    const grid = el("g", { class: "grid" }, svg);
    const axis = el("g", { class: "axis" }, svg);
    [0, 0.5, 1].forEach((f) => {
      const y = Math.round(Y(top * f)) + 0.5;
      el("line", { x1: pad.l, x2: W - pad.r, y1: y, y2: y }, grid);
      const label = el("text", { x: pad.l - 8, y: y + 3, "text-anchor": "end" }, axis);
      label.textContent = def.f(top * f);
    });
    const span = x1 - x0;
    const ticks = W < 380 ? 3 : 5;
    for (let i = 0; i < ticks; i++) {
      const ms = x0 + (span * i) / (ticks - 1);
      const label = el("text", { x: X(ms), y: H - 4, "text-anchor": i === 0 ? "start" : i === ticks - 1 ? "end" : "middle" }, axis);
      label.textContent = i === ticks - 1 ? "now" : timeLabel(ms, span);
    }
    if (def.threshold && def.max) {
      const y = Math.round(Y(def.threshold)) + 0.5;
      el("line", { class: "threshold", x1: pad.l, x2: W - pad.r, y1: y, y2: y }, svg);
    }

    const gap = Math.max(medianStep(t) * 3.5, 90e3);
    series.forEach((s, si) => {
      const values = data[s.key];
      let d = "", area = "", run = [];
      const flush = () => {
        if (run.length > 1) {
          const seg = run.map((p, j) => `${j ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
          d += seg;
          area += `${seg}L${X(run[run.length - 1][0]).toFixed(1)},${Y(0)}L${X(run[0][0]).toFixed(1)},${Y(0)}Z`;
        } else if (run.length === 1) {
          d += `M${X(run[0][0]).toFixed(1)},${Y(run[0][1]).toFixed(1)}h0.1`;
        }
        run = [];
      };
      for (let i = 0; i < t.length; i++) {
        if (values[i] == null || (run.length && t[i] - run[run.length - 1][0] > gap)) flush();
        if (values[i] != null) run.push([t[i], values[i]]);
      }
      flush();
      if (s.area) {
        const id = `fxa-${name}-${si}`;
        defs.insertAdjacentHTML("beforeend", `<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${s.color}" stop-opacity=".2"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></linearGradient>`);
        el("path", { d: area, fill: `url(#${id})` }, svg);
      }
      el("path", { d, class: `s-line${s.dash ? " s-dash" : ""}`, stroke: s.color }, svg);
    });
    c.cross = el("line", { class: "cross", y1: pad.t, y2: H - pad.b, x1: -10, x2: -10, visibility: "hidden" }, svg);
    c.dots = series.map((s) => el("circle", { class: "dot", r: 3.5, fill: s.color, visibility: "hidden" }, svg));
    c.svg = svg;
    paintHover(name);
  }

  function legendHTML(name, index) {
    const c = charts[name], def = CHARTS[name];
    return (c.series || []).map((s) => {
      const values = data[s.key];
      let v = null;
      if (index != null) v = values[index];
      else for (let i = values.length - 1; i >= 0; i--) if (values[i] != null) { v = values[i]; break; }
      return `<span><i style="background:${s.color}"></i>${s.label} <b>${def.f(v)}</b></span>`;
    }).join("");
  }

  function paintHover(name) {
    const c = charts[name];
    if (!c.scale) return;
    const t = data.t;
    const index = hoverTime == null ? null : nearestIndex(t, hoverTime);
    const valid = index != null && index >= 0 && Math.abs(t[index] - hoverTime) < Math.max(medianStep(t) * 3, 120e3);
    c.legend.innerHTML = legendHTML(name, valid ? index : null);
    if (!valid) {
      c.cross.setAttribute("visibility", "hidden");
      c.dots.forEach((d) => d.setAttribute("visibility", "hidden"));
      return;
    }
    const x = Math.round(c.scale.X(t[index])) + 0.5;
    c.cross.setAttribute("x1", x); c.cross.setAttribute("x2", x); c.cross.setAttribute("visibility", "visible");
    c.series.forEach((s, i) => {
      const v = data[s.key][index];
      const dot = c.dots[i];
      if (v == null) { dot.setAttribute("visibility", "hidden"); return; }
      dot.setAttribute("cx", x); dot.setAttribute("cy", c.scale.Y(v)); dot.setAttribute("visibility", "visible");
    });
  }

  let tip;
  function showTip(name) {
    const c = charts[name];
    if (!c.scale) return;
    const t = data.t, index = nearestIndex(t, hoverTime);
    if (index < 0) return;
    if (!tip) { tip = document.createElement("div"); tip.className = "fx-tip"; tip.setAttribute("role", "status"); }
    const rows = Object.keys(charts).flatMap((n) => (charts[n].series || []).map((s) => {
      const v = data[s.key][index];
      return `<div><i style="background:${s.color}"></i>${s.tip}<b>${CHARTS[n].f(v)}</b></div>`;
    }));
    tip.innerHTML = `<time>${fullTime(t[index])}</time>${rows.join("")}`;
    c.canvas.appendChild(tip);
    const box = c.canvas.getBoundingClientRect();
    const x = c.scale.X(t[index]);
    const half = tip.offsetWidth / 2 + 4;
    tip.style.left = `${Math.min(Math.max(x, half), box.width - half)}px`;
    tip.style.top = `${-tip.offsetHeight - 10}px`;
  }

  function bindHover(name) {
    const c = charts[name];
    const move = (e) => {
      if (!c.scale) return;
      const box = c.canvas.getBoundingClientRect();
      const px = (e.touches ? e.touches[0].clientX : e.clientX) - box.left;
      const { pad, W } = c.scale;
      const frac = Math.min(Math.max((px - pad.l) / (W - pad.l - pad.r), 0), 1);
      hoverTime = data.from + frac * (data.to - data.from);
      Object.keys(charts).forEach(paintHover);
      showTip(name);
    };
    const leave = () => { hoverTime = null; Object.keys(charts).forEach(paintHover); if (tip) tip.remove(); };
    c.canvas.addEventListener("pointermove", move);
    c.canvas.addEventListener("pointerleave", leave);
    c.canvas.addEventListener("touchmove", move, { passive: true });
    c.canvas.addEventListener("touchend", leave);
  }

  function renderAll() { Object.keys(charts).forEach(render); }
  Object.keys(charts).forEach(bindHover);
  renderAll();
  if ("ResizeObserver" in window) {
    let frame;
    const ro = new ResizeObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(renderAll); });
    Object.values(charts).forEach((c) => ro.observe(c.canvas));
  }

  // ---------------------------------------------------------------------------- range switching
  const rangeButtons = root.querySelectorAll("[data-fx-range]");
  async function loadRange(range) {
    rangeButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.fxRange === range)));
    root.dataset.range = range;
    const url = new URL(window.location.href);
    url.searchParams.set("range", range);
    history.replaceState(null, "", url);
    const response = await fetch(`${root.dataset.url}?range=${encodeURIComponent(range)}`, { credentials: "same-origin" });
    if (!response.ok) return;
    const fresh = await response.json();
    data = fresh.series;
    server = fresh.server;
    renderAll();
  }
  rangeButtons.forEach((b) => b.addEventListener("click", () => loadRange(b.dataset.fxRange)));

  // ---------------------------------------------------------------------------- live readings
  function setText(node, text) {
    if (node.textContent === text) return;
    node.textContent = text;
    node.classList.remove("fx-flash"); void node.offsetWidth; node.classList.add("fx-flash");
  }
  function updateTiles(s) {
    root.querySelectorAll("[data-fx-now] [data-k]").forEach((node) => {
      const key = node.dataset.k, kind = node.dataset.fmt || "num";
      setText(node, fmt[kind](s[key]));
    });
    root.querySelectorAll("[data-fx-now] [data-bar]").forEach((bar) => {
      const v = s[bar.dataset.bar];
      bar.style.width = `${v == null ? 0 : Math.min(v, 100)}%`;
      bar.className = `lv-${level(v)}`;
    });
    const seen = root.querySelector("[data-fx-seen]");
    if (seen && s.last_seen) seen.dataset.seen = s.last_seen;
  }
  function tickSeen() {
    const seen = root.querySelector("[data-fx-seen]");
    if (!seen || !seen.dataset.seen) return;
    const sec = Math.max(0, Math.round((Date.now() - Number(seen.dataset.seen)) / 1000));
    seen.textContent = sec < 60 ? `${sec}s ago` : sec < 3600 ? `${Math.floor(sec / 60)} min ago` : sec < 172800 ? `${Math.floor(sec / 3600)} h ago` : `${Math.floor(sec / 86400)} days ago`;
  }

  let lastSeries = Date.now();
  async function poll() {
    if (document.hidden) return;
    const wantSeries = ["1h", "24h"].includes(root.dataset.range) && Date.now() - lastSeries > SERIES_MS;
    try {
      const q = wantSeries ? `?range=${root.dataset.range}` : "?latest=1";
      const response = await fetch(root.dataset.url + q, { credentials: "same-origin" });
      if (!response.ok || response.redirected) return;
      const fresh = await response.json();
      server = fresh.server;
      if (signature(server) !== initialSignature) { window.location.reload(); return; }
      updateTiles(server);
      if (fresh.series) { data = fresh.series; lastSeries = Date.now(); renderAll(); }
    } catch (e) { /* keep the last good readings on screen */ }
  }
  setInterval(poll, LATEST_MS);
  setInterval(tickSeen, 1000);
  tickSeen();
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });

  // ---------------------------------------------------------------------------- copy IP
  root.querySelectorAll("[data-fx-copy]").forEach((button) => button.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(button.dataset.fxCopy); button.setAttribute("data-copied", ""); setTimeout(() => button.removeAttribute("data-copied"), 1600); }
    catch (e) { /* clipboard blocked: the text is still selectable */ }
  }));
  // close the pause menu when clicking elsewhere
  document.addEventListener("click", (e) => {
    root.querySelectorAll("details.fx-menu[open]").forEach((d) => { if (!d.contains(e.target)) d.removeAttribute("open"); });
  });
})();
