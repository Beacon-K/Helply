// Thumbs up / down on KB articles, updated in place (no reload, no scroll jump).
// Clicking the active thumb again removes the vote; clicking the other one switches it.
// A fresh thumbs-down opens an optional "suggest an improvement" box below the buttons.
(function () {
  const form = document.querySelector("[data-vote-form]");
  if (!form) return;
  const suggest = document.querySelector("[data-suggest]");
  const suggestForm = document.querySelector("[data-suggest-form]");
  const suggestDone = document.querySelector("[data-suggest-done]");

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      body,
      headers: { "X-Requested-With": "fetch" },
      credentials: "same-origin",
    }).then((response) => {
      if (!response.ok) throw new Error(`Request failed: ${response.status}`);
      return response.json();
    });
  }

  function showSuggest(show) {
    if (!suggest) return;
    suggest.hidden = !show;
    if (show) {
      suggestForm.hidden = false;
      suggestDone.hidden = true;
      suggestForm.querySelector("textarea").focus({ preventScroll: true });
    }
  }

  form.addEventListener("submit", async (event) => {
    const button = event.submitter;
    if (!button) return;
    event.preventDefault();

    const body = new FormData(form);
    body.set("vote", button.value);
    const buttons = form.querySelectorAll("button.vote");
    buttons.forEach((b) => (b.disabled = true));
    try {
      const state = await post(form.action, body);
      form.querySelector('[data-count="up"]').textContent = state.yes;
      form.querySelector('[data-count="down"]').textContent = state.no;
      buttons.forEach((b) => {
        const on = b.value === state.mine;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      showSuggest(state.mine === "down");
    } catch (error) {
      console.error(error);
    } finally {
      buttons.forEach((b) => (b.disabled = false));
    }
  });

  if (!suggestForm) return;

  suggestForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = suggestForm.querySelector("button.primary");
    submit.disabled = true;
    try {
      await post(suggestForm.action, new FormData(suggestForm));
      suggestForm.reset();
      suggestForm.hidden = true;
      suggestDone.hidden = false;
    } catch (error) {
      console.error(error);
    } finally {
      submit.disabled = false;
    }
  });

  document.querySelector("[data-suggest-dismiss]").addEventListener("click", () => showSuggest(false));
})();
