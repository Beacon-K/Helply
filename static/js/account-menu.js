/* The account menu in the top bar: opens on click, closes on an outside click or Escape,
   and hands focus back to its button so keyboard users are never lost. */
(function () {
  var root = document.querySelector("[data-acct]");
  if (!root) return;
  var button = root.querySelector(".acct-trigger");
  var menu = root.querySelector(".acct-menu");

  function setOpen(open) {
    menu.hidden = !open;
    button.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      var first = menu.querySelector("[role=menuitem]");
      if (first) first.focus();
    }
  }

  button.addEventListener("click", function () { setOpen(menu.hidden); });
  document.addEventListener("click", function (e) { if (!root.contains(e.target)) setOpen(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !menu.hidden) { setOpen(false); button.focus(); }
    if (menu.hidden || (e.key !== "ArrowDown" && e.key !== "ArrowUp")) return;
    var items = Array.prototype.slice.call(menu.querySelectorAll("[role=menuitem]"));
    var next = items.indexOf(document.activeElement) + (e.key === "ArrowDown" ? 1 : -1);
    items[(next + items.length) % items.length].focus();
    e.preventDefault();
  });
})();
