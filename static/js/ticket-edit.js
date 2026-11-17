/* Dropdowns marked data-autosave save as soon as another option is picked. The select is locked while
   the request is in flight so a second click cannot send a second change. */
(function () {
  document.querySelectorAll("form[data-autosave]").forEach(function (form) {
    var select = form.querySelector("select");
    if (!select) return;
    select.addEventListener("change", function () {
      select.classList.add("is-saving");
      form.submit();
      select.disabled = true;
    });
  });
})();
