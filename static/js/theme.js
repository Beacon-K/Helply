/* Light / dark switch. The inline script in <head> applies the saved (or system) theme before the
   first paint; this file handles the toggle button and follows the system setting until the user
   makes an explicit choice. The choice is a per-browser convenience, so storage failures are ignored. */
(function () {
  var root = document.documentElement;
  var KEY = "helply-theme";
  var meta = document.querySelector('meta[name="theme-color"]');

  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function apply(theme) {
    root.setAttribute("data-theme", theme);
    if (meta) meta.setAttribute("content", theme === "dark" ? "#060a13" : "#0b1b2b");
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) {
      b.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });
    document.dispatchEvent(new CustomEvent("helply:theme", { detail: { theme: theme } }));
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-theme-toggle]");
    if (!btn) return;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.classList.add("theme-anim"); // colours ease between themes, but only for this switch
    apply(next);
    try { localStorage.setItem(KEY, next); } catch (err) { /* private window: just don't remember */ }
    setTimeout(function () { root.classList.remove("theme-anim"); }, 450);
  });

  var mq = window.matchMedia && matchMedia("(prefers-color-scheme: dark)");
  if (mq && mq.addEventListener) {
    mq.addEventListener("change", function (e) { if (!stored()) apply(e.matches ? "dark" : "light"); });
  }
  apply(root.getAttribute("data-theme") || "light");
})();