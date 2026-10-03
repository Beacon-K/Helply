// Live updates for pages that show data other people can change (e.g. the asset register).
//
// The page declares   <div data-live data-live-url="..." data-live-version="..." data-live-interval="15">
// and marks updatable areas with  id="..." data-live-region.
// Every few seconds we ask the server for a tiny version string. Only when it differs do we
// fetch the page again and swap in the fresh regions - the search box, filters and scroll
// position are untouched. Rows with data-row-key / data-row-stamp are highlighted when they change.
(function () {
  const root = document.querySelector("[data-live]");
  if (!root) return;
  const interval = (parseInt(root.dataset.liveInterval, 10) || 15) * 1000;
  let version = root.dataset.liveVersion;
  let busy = false;

  function setStatus(text, state) {
    document.querySelectorAll("[data-live-status]").forEach((el) => {
      el.textContent = text;
      el.dataset.state = state || "ok";
    });
  }

  const now = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  function rowStamps() {
    const stamps = new Map();
    document.querySelectorAll("[data-row-key]").forEach((row) => stamps.set(row.dataset.rowKey, row.dataset.rowStamp));
    return stamps;
  }

  async function refresh() {
    const response = await fetch(location.href, { credentials: "same-origin" });
    if (!response.ok || response.redirected) throw new Error("refresh failed");
    const fresh = new DOMParser().parseFromString(await response.text(), "text/html");
    const before = rowStamps();
    document.querySelectorAll("[data-live-region]").forEach((region) => {
      const replacement = fresh.getElementById(region.id);
      if (replacement) region.replaceWith(document.adoptNode(replacement));
    });
    document.querySelectorAll("[data-row-key]").forEach((row) => {
      if (before.get(row.dataset.rowKey) !== row.dataset.rowStamp) row.classList.add("just-updated");
    });
  }

  async function check() {
    if (busy || document.hidden) return;
    busy = true;
    try {
      const response = await fetch(root.dataset.liveUrl, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "fetch" },
      });
      if (response.status === 404) {
        setStatus("This item was removed", "warn");
        return;
      }
      if (response.redirected) {
        setStatus("Signed out - reload to continue", "warn");
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const data = await response.json();
      if (data.version !== version) {
        await refresh();
        version = data.version;
        setStatus(`Updated ${now()}`, "fresh");
      } else {
        setStatus(`Live · checked ${now()}`);
      }
    } catch (error) {
      setStatus("Connection lost - retrying", "warn");
    } finally {
      busy = false;
    }
  }

  setStatus("Live");
  setInterval(check, interval);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) check();
  });
})();
