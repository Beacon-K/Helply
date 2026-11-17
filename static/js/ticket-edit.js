/* A field that already has a value starts locked; "Edit" unlocks it and reveals Save. */
(function () {
  document.querySelectorAll("form[data-edit-form]").forEach(function (form) {
    var field = form.querySelector("select, input");
    var edit = form.querySelector("[data-edit-btn]");
    var save = form.querySelector("[data-save-btn]");
    if (!field || !edit || !save) return;
    field.disabled = true;
    edit.addEventListener("click", function () {
      field.disabled = false;
      edit.hidden = true;
      save.hidden = false;
      field.focus();
    });
  });
})();
