/* People and SLA pages: clickable rows, copy button, team picker that follows the role, and a live
   "= 1 h 30 min" reading under each SLA time so nobody has to guess what "90" means. */
(function () {
  document.querySelectorAll("tr[data-href]").forEach(function (row) {
    row.addEventListener("click", function (e) { if (!e.target.closest("a, button")) location.href = row.dataset.href; });
  });

  document.querySelectorAll("[data-select-all]").forEach(function (el) { el.addEventListener("focus", function () { el.select(); }); });
  document.querySelectorAll("[data-copy-from]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var input = document.querySelector(btn.dataset.copyFrom);
      try { await navigator.clipboard.writeText(input.value); btn.textContent = "Copied"; }
      catch (e) { input.select(); btn.textContent = "Press Ctrl+C"; }
      setTimeout(function () { btn.textContent = "Copy"; }, 1800);
    });
  });

  var roles = document.querySelector("[data-roles]"), teams = document.querySelector("[data-teams]");
  if (roles && teams) {  // employees do not work tickets, so the team picker would do nothing for them
    var sync = function () {
      var picked = roles.querySelector("input:checked");
      teams.classList.toggle("is-muted", !!picked && picked.value === "employee");
    };
    roles.addEventListener("change", sync); sync();
  }

  var UNITS = { m: 1, min: 1, mins: 1, minute: 1, minutes: 1, h: 60, hr: 60, hrs: 60, hour: 60, hours: 60, d: 1440, day: 1440, days: 1440, w: 10080, week: 10080, weeks: 10080 };
  function minutes(text) {
    text = text.trim().toLowerCase();
    if (/^\d+$/.test(text)) return parseInt(text, 10);
    var re = /(\d+)\s*([a-z]+)/g, total = 0, m, used = "";
    while ((m = re.exec(text))) { if (!UNITS[m[2]]) return null; total += parseInt(m[1], 10) * UNITS[m[2]]; used += m[0]; }
    return used && text.replace(/\s+/g, "") === used.replace(/\s+/g, "") ? total : null;
  }
  function words(total) {
    var d = Math.floor(total / 1440), h = Math.floor((total % 1440) / 60), m = total % 60, out = [];
    if (d) out.push(d + (d === 1 ? " day" : " days")); if (h) out.push(h + (h === 1 ? " hour" : " hours")); if (m) out.push(m + " min");
    return out.join(" ") || "0 min";
  }
  document.querySelectorAll("[data-human]").forEach(function (hint) {
    var input = document.getElementById(hint.dataset.human), original = hint.textContent;
    var update = function () {
      var value = minutes(input.value);
      hint.textContent = value === null ? "Use a time like 30m, 4h or 1d 2h" : value ? "= " + words(value) : original;
    };
    input.addEventListener("input", update); update();
  });

  // Role buttons open a department list (with head counts). One menu at a time; click outside or Esc closes it.
  var pops = document.querySelectorAll("[data-pop]");
  function closePops(except) {
    pops.forEach(function (p) {
      if (p === except) return;
      var b = p.querySelector("[data-pop-btn]"), m = p.querySelector(".fx-pop-menu");
      b.setAttribute("aria-expanded", "false"); m.hidden = true;
    });
  }
  pops.forEach(function (pop) {
    var btn = pop.querySelector("[data-pop-btn]"), menu = pop.querySelector(".fx-pop-menu");
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = btn.getAttribute("aria-expanded") === "true";
      closePops(open ? null : pop);
      btn.setAttribute("aria-expanded", open ? "false" : "true"); menu.hidden = open;
      if (!open) { var first = menu.querySelector('[aria-current="true"]') || menu.querySelector("a"); if (e.detail === 0 && first) first.focus(); }
    });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });
  });
  document.addEventListener("click", function () { closePops(null); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var open = document.querySelector('[data-pop-btn][aria-expanded="true"]');
    closePops(null); if (open) open.focus();
  });})();
