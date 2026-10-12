// Helply Assistant panels: employee Q&A (data-ai-ask) and technician copilot (data-ai-copilot).
// Every piece of model output is inserted with textContent, never innerHTML, so a crafted
// ticket or article cannot inject markup into the page.
(function () {
  const DRAFT_KEY = "helply.ticketDraft";

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function section(title, body) {
    const wrap = el("div", "ai-sec");
    wrap.appendChild(el("h4", null, title));
    wrap.appendChild(body);
    return wrap;
  }

  function list(items, ordered) {
    const ul = el(ordered ? "ol" : "ul", "ai-list");
    items.forEach((text) => ul.appendChild(el("li", null, text)));
    return ul;
  }

  function links(items, label) {
    const ul = el("ul", "ai-links");
    items.forEach((item) => {
      const li = el("li");
      const a = el("a", null, label(item));
      a.href = item.url;
      li.appendChild(a);
      if (item.internal) li.appendChild(el("span", "ai-tag", "IT only"));
      if (item.status) li.appendChild(el("span", "ai-meta", item.status));
      if (item.resolution) li.appendChild(el("div", "ai-meta", "Resolved: " + item.resolution));
      ul.appendChild(li);
    });
    return ul;
  }

  async function post(panel, url, payload) {
    const token = panel.querySelector("input[name=csrfmiddlewaretoken]").value;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": token },
      body: JSON.stringify(payload || {}),
      credentials: "same-origin",
    });
    let data = {};
    try { data = await response.json(); } catch (e) { /* non-JSON error page */ }
    if (!response.ok) throw new Error(data.error || "The assistant could not answer. Please try again.");
    return data;
  }

  function busy(out, text) {
    out.hidden = false;
    out.replaceChildren(el("p", "ai-busy", text));
  }

  function failure(out, error) {
    out.hidden = false;
    out.replaceChildren(el("p", "ai-error", error.message));
  }

  function feedback(panel, id) {
    const row = el("div", "ai-feedback");
    row.appendChild(el("span", "ai-meta", "Was this helpful?"));
    ["Yes", "No"].forEach((label) => {
      const button = el("button", "ai-chip", label);
      button.type = "button";
      button.addEventListener("click", async () => {
        row.querySelectorAll("button").forEach((b) => (b.disabled = true));
        try {
          await post(panel, panel.dataset.feedbackBase.replace("/0/", "/" + id + "/"), { helpful: label === "Yes" });
          row.replaceChildren(el("span", "ai-meta", "Thanks for the feedback."));
        } catch (e) { row.replaceChildren(el("span", "ai-meta", e.message)); }
      });
      row.appendChild(button);
    });
    return row;
  }

  // ---------- employee ----------
  function initAsk(panel) {
    const form = panel.querySelector(".ai-form");
    const input = form.querySelector("textarea");
    const out = panel.querySelector(".ai-out");
    const submit = form.querySelector("button");

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); form.requestSubmit(); }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = input.value.trim();
      if (question.length < 3) return;
      submit.disabled = true;
      busy(out, "Looking through the knowledge base…");
      try {
        render(await post(panel, panel.dataset.url, { question }), question);
      } catch (error) { failure(out, error); }
      submit.disabled = false;
    });

    function ticketLink(question, primary) {
      const a = el("a", "btn" + (primary ? " primary" : ""), primary ? "Still need help? Open a ticket" : "Open a ticket");
      a.href = panel.dataset.ticketUrl;
      a.addEventListener("click", (event) => {
        try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ title: question.slice(0, 120), description: question })); } catch (e) { /* private mode */ }
        if (document.getElementById("id_description")) { event.preventDefault(); fillDraft(); }
      });
      return a;
    }

    function render(data, question) {
      out.hidden = false;
      out.replaceChildren();
      if (data.answer) out.appendChild(el("p", "ai-answer", data.answer));
      if (data.heads_up && data.heads_up.length) out.appendChild(section("Heads-up", list(data.heads_up)));
      if (data.past_tickets && data.past_tickets.length) {
        out.appendChild(section("Your earlier tickets", links(data.past_tickets, (t) => t.ref + " · " + t.title)));
      }
      if (data.articles && data.articles.length) {
        out.appendChild(section(data.ai ? "Sources" : "Related articles", links(data.articles, (a) => a.title)));
      }
      const actions = el("div", "ai-actions");
      actions.appendChild(ticketLink(question, data.needs_ticket));
      if (data.ai && data.id) actions.appendChild(feedback(panel, data.id));
      out.appendChild(actions);
    }
  }

  // ---------- technician ----------
  function initCopilot(panel) {
    const out = panel.querySelector(".ai-out");
    const run = panel.querySelector("[data-run]");
    run.addEventListener("click", async () => {
      run.disabled = true;
      busy(out, "Reading the ticket, its history and the knowledge base…");
      try { render(await post(panel, panel.dataset.url)); } catch (error) { failure(out, error); }
      run.disabled = false;
      run.textContent = "Analyze again";
    });

    function useAsComment(text) {
      const box = document.querySelector('form[action$="/comment/"] textarea');
      if (!box) return false;
      box.value = text;
      box.scrollIntoView({ behavior: "smooth", block: "center" });
      box.focus();
      return true;
    }

    function render(data) {
      out.hidden = false;
      out.replaceChildren();
      if (!data.ai) out.appendChild(el("p", "ai-error", "The AI assistant is not available right now. Related items are shown below."));
      if (data.summary) out.appendChild(section("Summary", el("p", null, data.summary)));
      if (data.likely_cause) out.appendChild(section("Likely cause", el("p", null, data.likely_cause)));
      if (data.steps.length) out.appendChild(section("Suggested steps", list(data.steps, true)));
      if (data.draft_reply) {
        const wrap = el("div");
        wrap.appendChild(el("p", "ai-draft", data.draft_reply));
        const row = el("div", "ai-actions");
        if (document.querySelector('form[action$="/comment/"] textarea')) {  // closed tickets have no comment form
          const use = el("button", "btn", "Use as comment");
          use.type = "button";
          use.addEventListener("click", () => { use.textContent = useAsComment(data.draft_reply) ? "Added to the comment box" : "Comment box not available"; });
          row.appendChild(use);
          wrap.appendChild(row);
        }
        out.appendChild(section("Draft reply (you review and send it)", wrap));
      }
      if (data.history_insight) out.appendChild(section("Requester history", el("p", null, data.history_insight)));
      if (data.potential_issues.length) out.appendChild(section("Potential issues", list(data.potential_issues)));
      if (data.articles.length) out.appendChild(section("Articles", links(data.articles, (a) => a.title)));
      if (data.similar_tickets.length) out.appendChild(section("Similar resolved tickets", links(data.similar_tickets, (t) => t.ref + " · " + t.title)));
      if (data.past_tickets.length) out.appendChild(section("Requester's recent tickets", links(data.past_tickets, (t) => t.ref + " · " + t.title)));
      if (data.ai && data.id) out.appendChild(feedback(panel, data.id));
    }
  }

  // ---------- hand a question over to the ticket form ----------
  function fillDraft() {
    const description = document.getElementById("id_description");
    const title = document.getElementById("id_title");
    if (!description) return;
    let draft = null;
    try { draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || "null"); sessionStorage.removeItem(DRAFT_KEY); } catch (e) { /* ignore */ }
    if (!draft) return;
    if (title && !title.value) title.value = String(draft.title || "").slice(0, 200);
    if (!description.value) description.value = String(draft.description || "");
    description.focus();
  }

  document.querySelectorAll("[data-ai-ask]").forEach((panel) => {
    panel.dataset.feedbackBase = panel.dataset.url.replace("ask/", "feedback/0/");
    initAsk(panel);
  });
  document.querySelectorAll("[data-ai-copilot]").forEach((panel) => {
    panel.dataset.feedbackBase = panel.dataset.url.replace(/ticket\/\d+\/$/, "feedback/0/");
    initCopilot(panel);
  });
  fillDraft();
  window.HelplyKit = { el, section, list, links, post, DRAFT_KEY };
})();

// ---------- Helply Assistant drawer (every page) and the admin insights card ----------
(function () {
  const kit = window.HelplyKit;
  const drawer = document.getElementById("ai-drawer");
  if (!kit || !drawer) return;
  const { el, section, links, post, DRAFT_KEY } = kit;
  const STORE = "helply.chat.v1";
  const log = drawer.querySelector(".aid-log");
  const welcome = drawer.querySelector(".aid-welcome");
  const form = drawer.querySelector(".aid-form");
  const input = form.querySelector("textarea");
  const send = form.querySelector("button");
  let messages = [];
  let waiting = false;

  try { messages = JSON.parse(sessionStorage.getItem(STORE) || "[]"); } catch (e) { messages = []; }
  if (!Array.isArray(messages)) messages = [];

  function save() {
    try { sessionStorage.setItem(STORE, JSON.stringify(messages.slice(-30))); } catch (e) { /* private mode */ }
  }

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function feedbackRow(id) {
    const row = el("div", "ai-feedback");
    row.appendChild(el("span", "ai-meta", "Helpful?"));
    ["Yes", "No"].forEach((label) => {
      const b = el("button", "ai-chip", label);
      b.type = "button";
      b.addEventListener("click", async () => {
        row.querySelectorAll("button").forEach((x) => (x.disabled = true));
        try {
          await post(drawer, drawer.dataset.feedback.replace("/0/", "/" + id + "/"), { helpful: label === "Yes" });
          row.replaceChildren(el("span", "ai-meta", "Thanks!"));
        } catch (e) { row.replaceChildren(el("span", "ai-meta", e.message)); }
      });
      row.appendChild(b);
    });
    return row;
  }

  function conversationSoFar(index) {
    // What the person told us so far becomes the starting text of the ticket.
    return messages.slice(0, index).filter((m) => m.role === "user").map((m) => m.text).slice(-4).join("\n");
  }

  function bubble(msg, index) {
    const wrap = el("div", "aid-msg " + msg.role);
    wrap.appendChild(el("div", "aid-text", msg.text));
    if (msg.role !== "assistant") return wrap;
    const d = msg.data || {};
    if (d.basis === "general") {
      wrap.appendChild(el("div", "aid-note", "General IT advice, not from our knowledge base or your tickets."));
    }
    if ((d.articles || []).length) wrap.appendChild(section("Sources", links(d.articles, (a) => a.title)));
    if ((d.tickets || []).length) wrap.appendChild(section("Tickets", links(d.tickets, (t) => t.ref + " · " + t.title)));
    if ((d.related || []).length) wrap.appendChild(section("Related articles", links(d.related, (a) => a.title)));
    const row = el("div", "ai-actions");
    if (d.suggest_ticket) {
      const a = el("a", "btn primary", "Open a ticket");
      a.href = drawer.dataset.ticketUrl;
      a.addEventListener("click", () => {
        const text = conversationSoFar(index);
        try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ title: text.split("\n")[0].slice(0, 120), description: text })); } catch (e) { /* ignore */ }
      });
      row.appendChild(a);
    }
    if (d.ai && d.id) row.appendChild(feedbackRow(d.id));
    if (row.childNodes.length) wrap.appendChild(row);
    return wrap;
  }

  function render() {
    log.querySelectorAll(".aid-msg, .aid-typing").forEach((n) => n.remove());
    welcome.hidden = messages.length > 0;
    messages.forEach((m, i) => log.appendChild(bubble(m, i)));
    if (waiting) log.appendChild(el("div", "aid-typing", "Thinking…"));
    scrollDown();
  }

  async function ask(text) {
    text = String(text || "").trim();
    if (text.length < 2 || waiting) return;
    open();
    const history = messages.slice(-6).map((m) => ({ role: m.role, text: m.text }));
    messages.push({ role: "user", text });
    waiting = true; send.disabled = true; input.value = ""; autosize();
    render(); save();
    try {
      const data = await post(drawer, drawer.dataset.url, { message: text, history });
      messages.push({ role: "assistant", text: data.reply, data });
    } catch (error) {
      messages.push({ role: "assistant", text: error.message, data: {} });
    }
    waiting = false; send.disabled = false;
    render(); save(); input.focus();
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 140) + "px";
  }

  function open() {
    drawer.hidden = false;
    requestAnimationFrame(() => drawer.classList.add("open"));
    document.body.classList.add("ai-open");
    render();
    input.focus();
  }

  function close() {
    drawer.classList.remove("open");
    document.body.classList.remove("ai-open");
    setTimeout(() => { if (!drawer.classList.contains("open")) drawer.hidden = true; }, 220);
  }

  function toggle() { drawer.classList.contains("open") ? close() : open(); }

  form.addEventListener("submit", (event) => { event.preventDefault(); ask(input.value); });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
  });
  drawer.querySelectorAll("[data-prompt]").forEach((b) => b.addEventListener("click", () => ask(b.dataset.prompt)));
  drawer.querySelector("[data-aid-close]").addEventListener("click", close);
  drawer.querySelector("[data-aid-new]").addEventListener("click", () => { messages = []; save(); render(); input.focus(); });
  document.querySelectorAll("[data-ai-open]").forEach((b) => b.addEventListener("click", toggle));
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "j") { event.preventDefault(); toggle(); }
    else if (event.key === "Escape" && drawer.classList.contains("open") && drawer.contains(document.activeElement)) close();
  });

  // Dashboard insights card: refresh the analysis, or hand a finding to the assistant.
  document.querySelectorAll("[data-ai-ask-about]").forEach((b) => b.addEventListener("click", () => ask(b.dataset.aiAskAbout)));
  document.querySelectorAll("[data-ai-insights-refresh]").forEach((b) => b.addEventListener("click", async () => {
    const card = b.closest(".ins");
    const original = b.textContent;
    b.disabled = true; b.textContent = "Analysing…";
    try {
      await post(card, b.dataset.url, {});
      location.reload();
    } catch (error) {
      b.textContent = error.message;
      setTimeout(() => { b.textContent = original; b.disabled = false; }, 4000);
    }
  }));

  window.HelplyAssistant = { open, close, toggle, ask };
})();
