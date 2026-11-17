/* Sign-in landing page: a slide deck.
   The sections are cards stacked on one screen. Wheel, swipe, arrow keys, the dots and the top links slide the
   next card up over the current one. A card taller than the window scrolls inside itself first, and only moves
   on once its own scrolling reaches the end. Without JavaScript (or when the deck cannot start) the sections are
   an ordinary page and the form still works. */
(function () {
  var root = document.documentElement;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var deck = document.querySelector("[data-deck]");
  var slides = deck ? Array.prototype.slice.call(deck.querySelectorAll("[data-slide]")) : [];

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

  if (!deck || slides.length < 2 || !root.classList.contains("lp-deck-on")) {
    root.classList.remove("lp-deck-on");
    return;
  }

  // The stage never scrolls. A #hash that matches an element (the sign-in card) or a focused field would
  // otherwise slide it, so any such movement is undone at once.
  [deck, document.body, root].forEach(function (el) {
    el.addEventListener("scroll", function () { if (el.scrollTop || el.scrollLeft) { el.scrollTop = 0; el.scrollLeft = 0; } }, { passive: true });
  });

  var cur = -1;
  var dotsBox = document.querySelector("[data-dots]");
  var count = document.querySelector("[data-count]");
  var prevBtn = document.querySelector("[data-prev]");
  var nextBtns = document.querySelectorAll("[data-next]");
  var navLinks = document.querySelectorAll("[data-slide-link]");
  var dots = [];

  slides.forEach(function (slide, i) {
    var dot = document.createElement("button");
    dot.type = "button";
    dot.dataset.label = slide.dataset.title || "";
    dot.setAttribute("aria-label", "Go to: " + (slide.dataset.title || "slide " + (i + 1)));
    dot.addEventListener("click", function () { go(i); });
    dotsBox.appendChild(dot);
    dots.push(dot);
  });

  function indexOfId(id) {
    for (var i = 0; i < slides.length; i++) if (slides[i].dataset.id === id) return i;
    return -1;
  }

  /* Paint the deck for slide n: earlier cards stack up behind it (each one a little smaller and darker),
     later cards wait below the screen. Cards that are not showing cannot be tabbed into. */
  function render(n) {
    slides.forEach(function (slide, i) {
      var d = n - i;
      slide.classList.toggle("is-active", d === 0);
      slide.classList.toggle("is-before", d > 0);
      slide.classList.toggle("is-after", d < 0);
      slide.style.setProperty("--depth", d > 0 ? d : 0);
      if (d === 0) { slide.removeAttribute("inert"); slide.removeAttribute("aria-hidden"); }
      else { slide.setAttribute("inert", ""); slide.setAttribute("aria-hidden", "true"); }
    });
    root.classList.toggle("lp-on-hero", n === 0);       // the first page keeps its own full-screen look
    root.classList.toggle("lp-past-first", n > 0);      // the back-to-start button only shows after it
    dots.forEach(function (dot, i) { dot.setAttribute("aria-current", i === n ? "true" : "false"); });
    navLinks.forEach(function (a) { a.setAttribute("aria-current", a.dataset.slideLink === slides[n].dataset.id ? "true" : "false"); });
    count.textContent = (n + 1) + " / " + slides.length;
    prevBtn.disabled = n === 0;
    nextBtns.forEach(function (b) { if (b.classList.contains("lp-pg")) b.disabled = n === slides.length - 1; });
  }

  var locked = false, unlockTimer = null;
  function go(n, opts) {
    n = Math.max(0, Math.min(slides.length - 1, n));
    if (n === cur) return;
    cur = n;
    render(n);
    var inner = slides[n].querySelector(".lp-slide-in");
    if (inner && !(opts && opts.keepScroll)) inner.scrollTop = 0;
    try { history.replaceState(null, "", "#" + slides[n].dataset.id); } catch (e) { /* the address bar is a nicety */ }
    lock(reduce ? 250 : 900);
  }
  function lock(ms) {
    locked = true;
    clearTimeout(unlockTimer);
    unlockTimer = setTimeout(function () { locked = false; }, ms);
  }
  function step(dir) { go(cur + dir); }

  /* A card that is taller than the window scrolls itself; return true when it can still move in this direction. */
  function innerCanScroll(dir) {
    var inner = slides[cur].querySelector(".lp-slide-in");
    if (!inner || inner.scrollHeight <= inner.clientHeight + 1) return false;
    return dir > 0 ? inner.scrollTop + inner.clientHeight < inner.scrollHeight - 1 : inner.scrollTop > 0;
  }

  // Mouse wheel and trackpad. Trackpad inertia keeps sending events after the gesture ends, so the lock only
  // opens again once the wheel has been quiet for a moment.
  var quietTimer = null;
  deck.addEventListener("wheel", function (e) {
    if (e.ctrlKey) return;  // pinch-zoom
    var dir = e.deltaY > 0 ? 1 : e.deltaY < 0 ? -1 : 0;
    if (!dir) return;
    if (innerCanScroll(dir)) return;  // let the card scroll itself
    e.preventDefault();
    if (locked) {
      clearTimeout(quietTimer);
      quietTimer = setTimeout(function () { locked = false; }, 140);
      return;
    }
    if (Math.abs(e.deltaY) < 6) return;
    step(dir);
  }, { passive: false });

  // Touch: swipe up for the next card, down for the one before; a card that was still scrolling at the start of
  // the swipe keeps it for scrolling.
  var touch = null;
  deck.addEventListener("touchstart", function (e) {
    if (e.touches.length !== 1) { touch = null; return; }
    touch = { y: e.touches[0].clientY, x: e.touches[0].clientX, canDown: innerCanScroll(1), canUp: innerCanScroll(-1) };
  }, { passive: true });
  deck.addEventListener("touchend", function (e) {
    if (!touch || locked) { touch = null; return; }
    var t = e.changedTouches[0], dy = touch.y - t.clientY, dx = touch.x - t.clientX;
    var begin = touch;
    touch = null;
    if (Math.abs(dy) < 56 || Math.abs(dy) < Math.abs(dx) * 1.3) return;
    if (dy > 0 && !begin.canDown) step(1);
    else if (dy < 0 && !begin.canUp) step(-1);
  }, { passive: true });

  // Keyboard, except while typing in a field.
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase();
    if (tag === "textarea" || tag === "select" || e.target.isContentEditable) return;
    // A single-line field has no use for the up/down keys, so they still turn the page (the sign-in
    // username is focused on arrival); every other key belongs to the field.
    if (tag === "input" && ["ArrowDown", "ArrowUp", "PageDown", "PageUp"].indexOf(e.key) < 0) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var k = e.key;
    if (k === "ArrowDown" || k === "PageDown" || (k === " " && !e.shiftKey)) { if (innerCanScroll(1)) return; e.preventDefault(); if (!locked) step(1); }
    else if (k === "ArrowUp" || k === "PageUp" || (k === " " && e.shiftKey)) { if (innerCanScroll(-1)) return; e.preventDefault(); if (!locked) step(-1); }
    else if (k === "Home") { e.preventDefault(); go(0); }
    else if (k === "End") { e.preventDefault(); go(slides.length - 1); }
  });

  var topBtn = document.querySelector("[data-top]");
  if (topBtn) topBtn.addEventListener("click", function () { go(0); });
  prevBtn.addEventListener("click", function () { step(-1); });
  nextBtns.forEach(function (b) { b.addEventListener("click", function (e) { e.preventDefault(); step(1); }); });
  navLinks.forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      var i = indexOfId(a.dataset.slideLink);
      if (i >= 0) go(i);
    });
  });
  document.querySelectorAll("[data-go]").forEach(function (a) {
    a.addEventListener("click", function (e) { e.preventDefault(); go(parseInt(a.dataset.go, 10) || 0); });
  });

  // "Sign in" links: back to the first card, cursor in the username field.
  document.querySelectorAll("[data-goto-signin]").forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      go(0);
      var field = document.querySelector("#signin input[name=username]");
      setTimeout(function () { if (field) field.focus({ preventScroll: true }); }, reduce ? 0 : 900);
    });
  });

  // A wrong password re-renders the first card; keep it as the starting point. A #hash picks the starting card.
  var start = indexOfId((location.hash || "").slice(1));
  if (document.querySelector(".lp-alert, .lp-err")) start = 0;
  cur = -1;
  // first paint without animating cards into place
  slides.forEach(function (s) { s.style.transition = "none"; });
  go(start >= 0 ? start : 0, { keepScroll: true });
  locked = false;
  requestAnimationFrame(function () { requestAnimationFrame(function () { slides.forEach(function (s) { s.style.transition = ""; }); }); });

  // an in-page anchor (#signin) can leave the card scrolled; always open on its top
  slides.forEach(function (sl) { var in_ = sl.querySelector(".lp-slide-in"); if (in_) in_.scrollTop = 0; });
  function settle() { deck.scrollTop = 0; deck.scrollLeft = 0; var in_ = slides[cur].querySelector(".lp-slide-in"); if (in_ && in_.scrollTop < 2) in_.scrollTop = 0; }
  settle();
  window.addEventListener("load", function () { settle(); setTimeout(settle, 60); });

  window.addEventListener("hashchange", function () {
    var i = indexOfId((location.hash || "").slice(1));
    if (i >= 0) go(i);
  });
})();
