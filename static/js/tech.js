/* Helply · console interactions (no libraries)
   - Command palette: Ctrl/Cmd+K (or "/") jumps to any page, a ticket by number, searches the knowledge base or assets,
     flips the theme, changes the password or logs out. Only pages the person can already see are offered.
   - Keyboard chords: "g" then d, t, n, k, a, s, p, l go to the matching page; "?" lists them.
   - A cursor spotlight on cards, a thin progress bar while a page loads, and a count-up on the headline numbers.
   Everything is optional: without JavaScript every page and link still works. */
(function () {
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- Cursor spotlight ----------
  var spot = null, spotFrame = 0, last = null;
  var CARD = ".card, .kpi, .fx-card, .fx-band, .fx-panel, .fx-sla-row, .fx-teamcard";
  document.addEventListener("pointermove", function (e) {
    if (e.pointerType === "touch") return;
    var el = e.target.closest ? e.target.closest(CARD) : null;
    if (!el) return;
    last = { el: el, x: e.clientX, y: e.clientY };
    if (!spotFrame) spotFrame = requestAnimationFrame(function () {
      spotFrame = 0;
      var r = last.el.getBoundingClientRect();
      last.el.style.setProperty("--mx", (last.x - r.left) + "px");
      last.el.style.setProperty("--my", (last.y - r.top) + "px");
    });
  }, { passive: true });

  // ---------- Progress bar while navigating ----------
  var bar = document.createElement("div"); bar.id = "tc-progress"; bar.setAttribute("aria-hidden", "true");
  document.body.appendChild(bar);
  var creep = 0;
  function startProgress() {
    if (reduce) return;
    bar.classList.add("is-on"); bar.style.width = "12%";
    clearInterval(creep);
    creep = setInterval(function () { var w = parseFloat(bar.style.width) || 0; bar.style.width = Math.min(w + (92 - w) * .12, 92) + "%"; }, 260);
  }
  function resetProgress() { clearInterval(creep); bar.style.width = "0"; bar.classList.remove("is-on"); }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target && a.target !== "_self" || a.hasAttribute("download")) return;
    var u; try { u = new URL(a.href, location.href); } catch (err) { return; }
    if (u.origin !== location.origin || (u.pathname === location.pathname && u.search === location.search) || u.hash && u.pathname === location.pathname) return;
    startProgress();
  });
  document.addEventListener("submit", function (e) { if (!e.defaultPrevented) startProgress(); });
  window.addEventListener("pageshow", resetProgress);

  // ---------- Count-up on headline numbers ----------
  function countUp(el) {
    var node = Array.prototype.find.call(el.childNodes, function (n) { return n.nodeType === 3 && /\d/.test(n.nodeValue); });
    if (!node) return;
    var m = node.nodeValue.match(/^(\D*)([\d,]+(?:\.\d+)?)(.*)$/s);
    if (!m) return;
    var target = parseFloat(m[2].replace(/,/g, "")), dec = (m[2].split(".")[1] || "").length, comma = m[2].indexOf(",") >= 0;
    if (!isFinite(target) || target === 0) return;
    var t0 = null, dur = Math.min(900, 380 + Math.log10(target + 1) * 160);
    function fmt(v) { var s = v.toFixed(dec); return comma ? Number(s).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec }) : s; }
    function frame(t) {
      if (t0 === null) t0 = t;
      var p = Math.min((t - t0) / dur, 1), eased = 1 - Math.pow(1 - p, 3);
      node.nodeValue = m[1] + fmt(target * eased) + m[3];
      if (p < 1) requestAnimationFrame(frame); else node.nodeValue = m[1] + m[2] + m[3];
    }
    requestAnimationFrame(frame);
  }
  if (!reduce && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { io.unobserve(en.target); countUp(en.target); } });
    }, { threshold: 0.4 });
    document.querySelectorAll(".kpi-value, .ov-big b, .ov-stats b").forEach(function (el) { io.observe(el); });
  }

  // ---------- Ticket references in monospace ----------
  document.querySelectorAll("a").forEach(function (a) { if (/^HLP-\d+$/.test(a.textContent.trim())) a.classList.add("ref"); });

  // ---------- Command palette ----------
  var nav = [];
  document.querySelectorAll(".side-nav a").forEach(function (a) {
    var label = (a.querySelector("span") || a).textContent.trim(), svg = a.querySelector("svg");
    nav.push({ label: label, href: a.getAttribute("href"), icon: svg ? svg.outerHTML : "" });
  });
  if (!nav.length) return;  // not signed in: nothing to offer
  var CHORDS = { d: "/", t: "/tickets/", n: "/tickets/new/", k: "/kb/", a: "/assets/", s: "/monitoring/", p: "/people/", l: "/sla/" };
  var chordNames = { d: "Dashboard", t: "Tickets", n: "New ticket", k: "Knowledge base", a: "Assets", s: "Cloud servers", p: "People", l: "SLA policies" };
  var has = function (href) { return nav.some(function (n) { return n.href === href; }); };
  var isMac = /Mac|iPhone|iPad/.test(navigator.platform);
  var mod = isMac ? "⌘" : "Ctrl";

  var SEARCH_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
  var overlay = document.createElement("div");
  overlay.className = "tc-overlay"; overlay.setAttribute("role", "dialog"); overlay.setAttribute("aria-modal", "true"); overlay.setAttribute("aria-label", "Command palette");
  overlay.innerHTML = '<div class="tc-palette"><div class="tc-search">' + SEARCH_ICON +
    '<input type="text" role="combobox" aria-expanded="true" aria-controls="tc-list" autocomplete="off" spellcheck="false" placeholder="Search or jump to…"><kbd>Esc</kbd></div>' +
    '<ul class="tc-list" id="tc-list" role="listbox"></ul>' +
    '<div class="tc-foot"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span><kbd>?</kbd> shortcuts</span></div></div>' +
    '<div class="tc-palette tc-sheetwrap" hidden></div>';
  document.body.appendChild(overlay);
  var input = overlay.querySelector("input"), list = overlay.querySelector(".tc-list"), items = [], index = 0, opener = null;
var searchPanel = overlay.querySelector(".tc-palette"), sheetPanel = overlay.querySelector(".tc-sheetwrap");

  var trigger = document.querySelector("[data-cmdk]");
  if (trigger) { trigger.querySelector("kbd").textContent = mod + " K"; trigger.addEventListener("click", function () { openPalette(); }); }

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function chordFor(href) { for (var k in CHORDS) if (CHORDS[k] === href) return k.toUpperCase(); return ""; }

  function build(q) {
    q = q.trim(); var out = [], lower = q.toLowerCase();
    var num = q.match(/^(?:hlp-?|#)?0*(\d{1,6})$/i);
    if (num) out.push({ group: "Ticket", label: "Open ticket HLP-" + ("00000" + num[1]).slice(-5), href: "/tickets/" + parseInt(num[1], 10) + "/", sub: "by number", icon: (nav.filter(function (n) { return n.href === "/tickets/"; })[0] || nav[0]).icon });
    var pages = nav.filter(function (n) { return !lower || n.label.toLowerCase().indexOf(lower) >= 0; })
      .map(function (n) { return { group: "Go to", label: n.label, href: n.href, icon: n.icon, key: chordFor(n.href) }; });
    out = out.concat(pages);
    var actions = [
      { group: "Actions", label: "Switch light / dark theme", run: function () { var b = document.querySelector("[data-theme-toggle]"); if (b) b.click(); }, icon: '<svg viewBox="0 0 24 24"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/></svg>' },
      { group: "Actions", label: "Notifications", href: "/notifications/", icon: '<svg viewBox="0 0 24 24"><path d="M6 9a6 6 0 1 1 12 0c0 6 2.5 7 2.5 7h-17S6 15 6 9Z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>' },
      { group: "Actions", label: "Change password", href: "/accounts/password_change/", icon: '<svg viewBox="0 0 24 24"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>' },
      { group: "Actions", label: "Keyboard shortcuts", run: showSheet, key: "?", icon: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10"/></svg>' },
      { group: "Actions", label: "Log out", run: function () { var b = document.querySelector('form[action*="logout"] button'); if (b) b.click(); }, icon: '<svg viewBox="0 0 24 24"><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H4"/></svg>' }
    ].filter(function (a) { return !lower || a.label.toLowerCase().indexOf(lower) >= 0; });
    out = out.concat(actions);
    if (q.length > 1 && !num) {
      out.push({ group: "Search", label: "Search the knowledge base for “" + q + "”", href: "/kb/?q=" + encodeURIComponent(q), icon: nav.filter(function (n) { return n.href === "/kb/"; }).map(function (n) { return n.icon; })[0] || SEARCH_ICON });
      if (has("/assets/") && nav.some(function (n) { return n.href === "/assets/" && n.label === "Assets"; })) {
        out.push({ group: "Search", label: "Search assets for “" + q + "”", href: "/assets/?q=" + encodeURIComponent(q), icon: nav.filter(function (n) { return n.href === "/assets/"; }).map(function (n) { return n.icon; })[0] });
      }
    }
    return out;
  }
  function render() {
    items = build(input.value); index = Math.min(index, Math.max(items.length - 1, 0));
    if (!items.length) { list.innerHTML = '<li class="tc-empty">Nothing matches “' + esc(input.value) + '”.</li>'; return; }
    var html = "", group = "";
    items.forEach(function (it, i) {
      if (it.group !== group) { group = it.group; html += '<li class="tc-group" role="presentation">' + esc(group) + "</li>"; }
      html += '<li class="tc-item" role="option" id="tc-opt-' + i + '" data-i="' + i + '" aria-selected="' + (i === index) + '">' + (it.icon || "") + "<span>" + esc(it.label) + "</span>" +
        (it.sub ? '<span class="tc-sub">' + esc(it.sub) + "</span>" : "") +
        (it.key ? '<span class="tc-hint">' + (it.key === "?" ? "<kbd>?</kbd>" : "<kbd>G</kbd><kbd>" + esc(it.key) + "</kbd>") + "</span>" : "") + "</li>";
    });
    list.innerHTML = html;
    var sel = list.querySelector('[aria-selected="true"]'); if (sel) { input.setAttribute("aria-activedescendant", sel.id); sel.scrollIntoView({ block: "nearest" }); }
  }
  function choose(i) {
    var it = items[i]; if (!it) return; closePalette();
    if (it.run) it.run(); else if (it.href) { startProgress(); location.href = it.href; }
  }
  function openPalette() {
    if (!overlay.classList.contains("is-open")) opener = document.activeElement;
    overlay.classList.add("is-open"); searchPanel.hidden = false; sheetPanel.hidden = true;
    input.value = ""; index = 0; render(); setTimeout(function () { input.focus(); }, 0);
  }
  function closePalette() { overlay.classList.remove("is-open"); if (opener && opener.focus) opener.focus(); }
  function showSheet() {
    if (!overlay.classList.contains("is-open")) opener = document.activeElement;
    var rows = Object.keys(CHORDS).filter(function (k) { return has(CHORDS[k]); }).map(function (k) { return "<dt>" + chordNames[k] + "</dt><dd><kbd>G</kbd><kbd>" + k.toUpperCase() + "</kbd></dd>"; }).join("");
    sheetPanel.innerHTML = '<div class="tc-sheet"><h2>Keyboard shortcuts</h2><dl><dt>Open the command palette</dt><dd><kbd>' + mod + '</kbd><kbd>K</kbd></dd>' + rows + '<dt>This list</dt><dd><kbd>?</kbd></dd></dl></div>';
    overlay.classList.add("is-open"); searchPanel.hidden = true; sheetPanel.hidden = false; sheetPanel.tabIndex = -1; sheetPanel.focus();
  }
  list.addEventListener("click", function (e) { var li = e.target.closest(".tc-item"); if (li) choose(parseInt(li.dataset.i, 10)); });
  list.addEventListener("pointermove", function (e) { var li = e.target.closest(".tc-item"); if (li && parseInt(li.dataset.i, 10) !== index) { index = parseInt(li.dataset.i, 10); list.querySelectorAll(".tc-item").forEach(function (n) { n.setAttribute("aria-selected", n.dataset.i == index); }); } });
  input.addEventListener("input", function () { index = 0; render(); });
  overlay.addEventListener("mousedown", function (e) { if (e.target === overlay) closePalette(); });
  overlay.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { e.preventDefault(); closePalette(); }
    else if (e.key === "ArrowDown" || (e.key === "n" && e.ctrlKey)) { e.preventDefault(); index = (index + 1) % Math.max(items.length, 1); render(); }
    else if (e.key === "ArrowUp" || (e.key === "p" && e.ctrlKey)) { e.preventDefault(); index = (index - 1 + items.length) % Math.max(items.length, 1); render(); }
    else if (e.key === "Enter") { e.preventDefault(); choose(index); }
    else if (e.key === "Tab") { e.preventDefault(); }
  });

  // ---------- Global keys ----------
  var chord = 0;
  function typing(e) { var t = e.target; return t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)); }
  document.addEventListener("keydown", function (e) {
    if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); if (overlay.classList.contains("is-open") && !searchPanel.hidden) closePalette(); else openPalette(); return; }
    if (overlay.classList.contains("is-open") && e.key === "Escape") { e.preventDefault(); closePalette(); return; }
    if (typing(e) || e.ctrlKey || e.metaKey || e.altKey || overlay.classList.contains("is-open")) return;
    if (e.key === "/") { e.preventDefault(); openPalette(); return; }
    if (e.key === "?") { e.preventDefault(); showSheet(); return; }
    if (chord) {
      var href = CHORDS[e.key.toLowerCase()]; chord = 0;
      if (href && has(href)) { e.preventDefault(); startProgress(); location.href = href; }
      return;
    }
    if (e.key === "g" || e.key === "G") { chord = 1; setTimeout(function () { chord = 0; }, 1200); }
  });
})();
