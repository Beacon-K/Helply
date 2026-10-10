/* Sign-in landing page: reveal on scroll, a solid navigation bar after the hero, a gentle parallax on the big photo,
   a show/hide password button, and "Sign in" links that scroll to the card and focus the first field.
   Everything degrades: without JavaScript the page is fully visible and the form still works. */
(function () {
  var root = document.documentElement;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Reveal elements as they enter the viewport (elements already visible show immediately).
  var items = document.querySelectorAll(".reveal, .lp-sla");
  if (reduce || !("IntersectionObserver" in window)) {
    items.forEach(function (el) { el.classList.add("is-in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add("is-in"); io.unobserve(entry.target); }
      });
    }, { threshold: 0.14, rootMargin: "0px 0px -6% 0px" });
    items.forEach(function (el) { io.observe(el); });
  }

  // Navigation: transparent over the hero, frosted afterwards (light text on dark sections, dark text on light ones).
  var nav = document.querySelector("[data-nav]"), hero = document.querySelector(".lp-hero");
  function lightSectionUnderNav() {
    if (root.getAttribute("data-theme") === "dark") return false;
    var y = 28, els = document.elementsFromPoint(window.innerWidth / 2, y);
    for (var i = 0; i < els.length; i++) {
      var s = els[i].closest && els[i].closest(".lp-feature, .lp-bento-sec, .lp-trust");
      if (s) return !s.classList.contains("dark");
    }
    return false;
  }
  function paintNav() {
    if (!nav) return;
    var past = window.scrollY > 24;
    nav.classList.toggle("is-solid", past);
    nav.classList.toggle("is-light", past && lightSectionUnderNav());
  }

  // Parallax: the big photo drifts and settles as it crosses the screen.
  var frame = document.querySelector("[data-parallax]"), ticking = false;
  function parallax() {
    ticking = false;
    if (!frame || reduce) return;
    var r = frame.getBoundingClientRect(), vh = window.innerHeight;
    var p = Math.min(Math.max((vh - r.top) / (vh + r.height), 0), 1);  // 0 as it enters, 1 as it leaves
    frame.style.setProperty("--s", (1.14 - p * 0.1).toFixed(3));
    frame.style.setProperty("--y", ((p - 0.5) * -28).toFixed(1) + "px");
  }
  function onScroll() { paintNav(); if (!ticking) { ticking = true; requestAnimationFrame(parallax); } }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  document.addEventListener("helply:theme", paintNav);
  onScroll();

  // "Sign in" links go to the card and put the cursor in the username field.
  document.querySelectorAll("[data-goto-signin]").forEach(function (link) {
    link.addEventListener("click", function (e) {
      var card = document.getElementById("signin");
      if (!card) return;
      e.preventDefault();
      card.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
      var field = card.querySelector("input[type=text], input[name=username]");
      setTimeout(function () { if (field) field.focus({ preventScroll: true }); }, reduce ? 0 : 650);
    });
  });

  // Show or hide the password.
  var eye = document.querySelector("[data-eye]");
  if (eye) {
    eye.addEventListener("click", function () {
      var input = eye.parentNode.querySelector("input");
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      eye.setAttribute("aria-pressed", show ? "true" : "false");
      eye.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  }
})();
