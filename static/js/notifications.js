// Keeps the notification bell's unread count current without reloading the page.
(function () {
  const bell = document.querySelector("[data-bell]");
  if (!bell) return;
  const badge = bell.querySelector("[data-unread]");

  function render(count) {
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = count === 0;
    bell.setAttribute("aria-label", count ? `Notifications, ${count} unread` : "Notifications");
  }

  async function refresh() {
    if (document.hidden) return;
    try {
      const response = await fetch(bell.dataset.url, { credentials: "same-origin" });
      if (response.ok) render((await response.json()).unread);
    } catch (error) {
      /* offline or signed out: keep the last known count */
    }
  }

  setInterval(refresh, 60000);
  document.addEventListener("visibilitychange", refresh);
})();
