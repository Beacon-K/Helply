/* Help & guided tour.
 * A "Help" button at the bottom of the sidebar opens a menu of short lessons. Each lesson is a
 * spotlight tour: some steps ask the person to CLICK the highlighted item (learning by doing),
 * others just explain. The tour follows the person from page to page; its position is kept in
 * sessionStorage, so it survives the page loads, and it is cleared when the tab closes.
 * Lessons are filtered by role, so nobody is shown a page they cannot open. */
(function () {
  "use strict";
  var btn = document.querySelector("[data-help-open]");
  if (!btn) return;
  var role = btn.getAttribute("data-role") || "employee";
  var isAgent = role === "technician" || role === "administrator";
  var isAdmin = role === "administrator";
  var KEY = "helply-tour";
  var isMac = /Mac|iPhone|iPad/.test(navigator.platform);
  var mod = isMac ? "⌘" : "Ctrl";

  var nav = function (href) { return '.side-nav a[href="' + href + '"]'; };

  /* ---- Lessons. step: {path, target, title, body, click} ----
   * path   page the step lives on (omit = any page); the tour navigates there when needed.
   * target CSS selector to spotlight (omit or not found = centred card).
   * click  true = the person must click the target to continue. */
  var TOPICS = [
    { id: "dashboard", title: "Dashboard", desc: "Your overview, the menu, search, the Assistant and your account.", roles: ["employee", "technician", "administrator"], steps: [
      { path: "/", target: "h1", title: "Your dashboard", body: isAdmin ? "This is the company overview: tickets waiting for an owner, SLA risk, people, cloud servers and renewals. Everything here is live." : isAgent ? "Your queue and the tickets that need attention first. It updates as work comes in." : "Your open requests and what is happening with them, at a glance." },
      { path: "/", target: ".self-help", emp: true, optional: true, title: "Ask Helply first", body: "Type your problem in your own words. The Assistant answers from the knowledge base and your own past tickets; if it cannot help, one click opens a ticket." },
      { path: "/", target: ".confirm-card", emp: true, optional: true, title: "Confirm it is fixed", body: "When IT resolves a ticket, it appears here so you can confirm and rate the fix. Resolved tickets close by themselves after a reminder." },
      { path: "/", target: "#dash-mine", emp: true, optional: true, title: "My open tickets", body: "Each ticket shows who is working on it and a progress bar of where it stands. Click one to read the conversation. Recently closed tickets are listed below." },
      { path: "/", target: "#dash-popular", emp: true, optional: true, title: "Popular answers", body: "The knowledge base articles other people read most." },
      { path: "/", target: "#dash-urgent", emp: true, optional: true, title: "Urgent?", body: "A suspicious link, a lost device or an office-wide outage should not wait: open a ticket with Impact and Urgency set to High." },
      { path: "/", target: ".kpis", tech: true, optional: true, title: "Your numbers", body: "Your open tickets, tickets nobody owns yet, urgent ones that are at risk or breached, what you resolved in the last 7 days, and your average satisfaction rating." },
      { path: "/", target: "#dash-queue", tech: true, optional: true, title: "My queue", body: "Your open tickets with the most urgent first. The coloured label shows whether the SLA is breached, at risk, paused while you wait on someone, or on track." },
      { path: "/", target: "#dash-awaiting", tech: true, optional: true, title: "Waiting for the requester", body: "Tickets you resolved that the requester has not confirmed yet." },
      { path: "/", target: "#dash-unassigned", tech: true, optional: true, title: "Waiting for a technician", body: "Open tickets that nobody owns yet. Open one to take it." },
      { path: "/", target: ".kpis", admin: true, optional: true, title: "Key numbers", body: "Open tickets, unassigned tickets, SLA risk (breached and at risk), SLA met over 30 days, customer satisfaction, and how often the AI category suggestion was right. Open tickets and Unassigned are links to the matching lists." },
      { path: "/", target: "#dash-attention", admin: true, optional: true, title: "Needs attention", body: "Tickets that are breached, at risk or still unassigned, most important first, each with its priority and due time." },
      { path: "/", target: "#dash-stages", admin: true, optional: true, title: "Open work by stage", body: "How many open tickets are in each stage, from not started to resolved. Click a bar to see them." },
      { path: "/", target: "#dash-workload", admin: true, optional: true, title: "Team workload", body: "Open tickets per technician, plus the unassigned pile. A red note shows how many of someone's tickets are at risk." },
      { path: "/", target: "#ai-insights", admin: true, optional: true, title: "AI insights", body: "Helply looks at recent tickets for problems that keep coming back, explains the likely cause and how to prevent it, and lists tickets and devices involved. It runs once a day; press the button to run it now, and use Ask the assistant to dig deeper." },
      { path: "/", target: "#ai-usage", admin: true, optional: true, title: "AI usage today", body: "How much of the daily AI allowance has been used, how many are left and when it resets, a breakdown by model, and the last 7 days. When it runs out, AI falls back to keyword matching." },
      { path: "/", target: ".ov-title", admin: true, optional: true, title: "Company overview", body: "Three summaries of the rest of the company, each with a link to its full page." },
      { path: "/", target: "#ov-servers", agent: true, optional: true, title: "Cloud servers", body: "How many servers are healthy, need attention or are offline, average CPU, open alerts and monthly cost, with the servers listed below." },
      { path: "/", target: "#ov-people", admin: true, optional: true, title: "People", body: "Active people by role and by department, and how many accounts are turned off." },
      { path: "/", target: "#ov-renewals", agent: true, optional: true, title: "Renewals and assets", body: "Subscriptions and warranties due in the next 30 days, plus counts of assets, expired warranties and devices in repair." },
      { target: ".sidebar .side-nav", title: "The menu", body: "Every area of Helply is here. On a phone this becomes the row of icons along the top." },
      { target: "[data-cmdk]", click: true, title: "Search everything", body: "Click here (or press " + mod + " K) to open the command palette. Type a page name or a ticket number such as 42 and press Enter." },
      { target: ".tc-palette", ui: "palette", title: "The command palette", body: "Pages, tickets and actions in one list. Tip: press G and then a letter (G T for Tickets) to jump without the mouse. Press Esc to close.", needsOpen: true },
      { target: "[data-ai-open]", click: true, title: "Ask the Assistant", body: "Click Assistant (or press " + mod + " J). It answers from your company's knowledge base" + (isAgent ? " and ticket history" : " and your own past tickets") + ", and tells you when an answer is general IT advice instead." },
      { target: "#ai-drawer", ui: "drawer", title: "A real conversation", body: "Ask follow-up questions; it remembers the conversation. Close it with Esc.", needsOpen: true },
      { target: "[data-bell]", title: "Notifications", body: "A number appears here when a ticket you follow changes. Click the bell any time to see them all." },
      { target: ".who-name", title: "Your account", body: "Your name and role. Click it to change your password. Log out is next to it." },
      { target: "[data-theme-toggle]", title: "Light or dark", body: "Pick whichever is easier on your eyes. Helply remembers your choice." }
    ] },
    { id: "tickets", title: "Tickets", desc: isAgent ? "Filter, open, update and resolve." : "See status and reply to technicians.", roles: ["employee", "technician", "administrator"], steps: [
      { target: nav("/tickets/"), click: true, title: "Open the tickets list", body: "Click \"Tickets\"." },
      { path: "/tickets/", target: ".filters", title: "Filter by status", body: "Switch between open, in progress, resolved and more. The list always shows the most important first." },
      { path: "/tickets/", target: ".table-wrap", title: "Open a ticket", body: isAgent ? "Click any row to open it. Inside you can change status, reassign, add notes, and get an AI copilot summary with similar past tickets." : "Click any row to see the conversation, add details, and follow progress. Priority and SLA status are shown in the columns." }
    ] },
    { id: "ticket", title: "New ticket", desc: "Describe the problem once, and Helply routes it.", roles: ["employee", "technician", "administrator"], steps: [
      { target: nav("/tickets/new/"), click: true, title: "Start a new ticket", body: "Click \"New ticket\" in the menu." },
      { path: "/tickets/new/", target: "[data-ai-ask]", title: "Try the Assistant first", body: "Describe your problem here. If the knowledge base already has the answer you'll see it immediately; if not, one click turns your question into a ticket.", optional: true },
      { path: "/tickets/new/", target: "#id_department", agent: true, optional: true, title: "Raising it for someone else", body: "Technicians and administrators can log a ticket for a colleague. Pick their department first to narrow the list." },
      { path: "/tickets/new/", target: "#id_requester", agent: true, optional: true, title: "Who is it for?", body: "Choose the employee, or leave \"Myself\" to log your own issue. The colleague is the requester and is notified of every update." },
      { path: "/tickets/new/", target: "#id_title", title: "A short title", body: "Say what is wrong in one line, for example \"VPN disconnects every few minutes\". It is what everyone sees in lists and notifications." },
      { path: "/tickets/new/", target: "#id_description", title: "Describe the problem", body: "What happened, what you expected, and anything you already tried. Helply suggests a category and priority from your words, so details help. Please do not paste passwords." },
      { path: "/tickets/new/", target: "#id_category", title: "Category", body: "Leave \"Not sure\" and Helply decides. When it is confident it also triages and routes the ticket to the right team automatically; you can always change it later." },
      { path: "/tickets/new/", target: "#id_asset", title: "Which device?", body: "Link the laptop, phone or other equipment the problem is about, so the ticket carries its history. " + (isAgent ? "Only devices that have an owner are listed." : "Only your own devices are listed.") },
      { path: "/tickets/new/", target: "#id_impact", title: "Impact", body: "How many people, or how much of the business, is affected? One person is low; the whole office is high." },
      { path: "/tickets/new/", target: "#id_urgency", title: "Urgency", body: "How quickly does it need fixing? Impact and urgency together set the priority from P1 to P4 using the ITIL matrix, and the priority decides the SLA clock." },
      { path: "/tickets/new/", target: "form[method=post] button[type=submit], form[method=post] .btn.primary", title: "Submit", body: "You'll get notified on every update, and an SLA clock starts so nothing gets forgotten. (Nothing is sent until you click this.)" }
    ] },
    { id: "kb", title: "Knowledge base", desc: "Step-by-step answers written by IT.", roles: ["employee", "technician", "administrator"], steps: [
      { target: nav("/kb/"), click: true, title: "Open the knowledge base", body: "Click \"Knowledge base\"." },
      { path: "/kb/", target: "[data-ai-ask]", title: "Ask the Assistant", body: "Describe your problem in your own words before opening a ticket: the Assistant answers from the knowledge base. Many problems (Wi-Fi, VPN, printers, passwords) already have a guide." },
      { path: "/kb/", target: ".filters", title: "Browse by category", body: "Pick a category to narrow the list; the number beside each name is how many articles it holds. \"All\" shows everything." },
      { path: "/kb/", target: "a[href='/kb/new/']", agent: true, title: "Write an article", body: "Technicians and administrators add and edit articles right here. Employees only read them." },
      { path: "/kb/", target: "#kb-open-ticket", title: "Can't find an answer?", body: "This button opens a new ticket whenever the knowledge base does not have what you need." },
      { path: "/kb/", target: "#kb-popular", title: "Most viewed", body: "The guides people open most. If your question is common, the answer is probably here." },
      { path: "/kb/", target: "#kb-urgent", title: "Urgent?", body: "A suspicious link, a lost device or an office-wide outage should not wait for an article: open a ticket with Impact and Urgency set to High." },
      { path: "/kb/", target: ".kb-item a", click: true, title: "Open an article", body: "Click any article. " + (isAgent ? "Labels beside a title show \"IT only\" articles, drafts, and how many reader suggestions are waiting." : "The short summary under each title tells you whether it is the right one.") },
      { target: ".kb-article h1", optional: true, title: "Reading an article", body: "The steps are written by IT. Under the title you can see when it was last updated and how many times it has been read." },
      { target: "#feedback", optional: true, title: "Did it solve your problem?", body: "Press Yes or No. Click again to undo. Your answer helps IT see which guides work, and it improves the Assistant's answers." },
      { target: "[data-suggest-form], #feedback", optional: true, title: "Suggest an improvement", body: "If you press No, a box opens where you can say what was missing or wrong. It goes straight to IT, and you can open a ticket from there if you still need help." },
      { target: ".kb-article .row-between div", agent: true, optional: true, title: "Edit or delete", body: "Technicians and administrators can edit or delete the article here." },
      { target: "#suggestions", agent: true, optional: true, title: "Reader suggestions", body: "What readers said was missing or wrong. Mark a suggestion as addressed once you have fixed the article; you can reopen it later." },
      { target: "#kb-stuck", optional: true, title: "Still stuck?", body: "Opens a new ticket with the category and this article already filled in, so IT knows what you tried." },
      { target: "#kb-related", optional: true, title: "Related articles", body: "Other guides on the same topic." }
    ] },
    { id: "assets", title: isAgent ? "Assets" : "My devices", desc: isAgent ? "Every laptop, phone and licence in one place." : "See the devices assigned to you.", roles: ["employee", "technician", "administrator"], steps: [
      { target: nav("/assets/"), click: true, title: isAgent ? "Open the asset register" : "Open My devices", body: "Click the highlighted menu item." },
      { path: "/assets/", target: ".asset-toolbar, main .card", title: isAgent ? "Find and filter assets" : "Your equipment", body: isAgent ? "Search by name, serial number or owner, and filter by type or status. Open an asset to see its history and linked tickets." : "Everything IT has assigned to you. If something is broken, open the device and report an issue from there so the ticket already knows which machine it is." }
    ] },
    { id: "servers", title: "Cloud servers", desc: "Live health of your servers, with alerts that open tickets.", roles: ["technician", "administrator"], steps: [
      { target: nav("/monitoring/"), click: true, title: "Open Cloud servers", body: "Click \"Cloud servers\"." },
      { path: "/monitoring/", target: ".fx-empty", optional: true, title: "No servers yet", body: "Add a server and Helply gives you a one-line install command for Linux or Windows. Once the small read-only agent reports in, everything below appears on its own." },
      { path: "/monitoring/", target: ".fx-lede", optional: true, title: "Status at a glance", body: "One line tells you whether everything is fine, how many servers are offline or need attention, or that an agent is still being set up. It refreshes by itself, so there is no need to reload." },
      { path: "/monitoring/", target: ".fx-cell:nth-child(1)", optional: true, title: "Fleet health", body: "How many servers are online out of the total, split into healthy, attention, offline and waiting for their first report." },
      { path: "/monitoring/", target: ".fx-cell:nth-child(2)", optional: true, title: "Average CPU", body: "The average processor load across the servers that are online right now." },
      { path: "/monitoring/", target: ".fx-cell:nth-child(3)", optional: true, title: "Open alerts", body: "Problems that are still open. Each one is tracked by a ticket, so nothing depends on someone noticing a graph." },
      { path: "/monitoring/", target: ".fx-cell:nth-child(4)", optional: true, title: "Cloud spend", body: "What your servers cost per month, and which renewal is coming up next. Renewal dates come from the cost details saved for each server." },
      { path: "/monitoring/", target: ".fx-search", optional: true, title: "Find a server", body: "Search by name, purpose, provider, region, country, IP address, hostname, system or owner." },
      { path: "/monitoring/", target: ".fx-seg-filter", optional: true, title: "Filter by status", body: "Show everything, or only healthy servers, those that need attention, or those that are offline." },
      { path: "/monitoring/", target: ".fx-seg-view", optional: true, title: "Cards or table", body: "Cards show each server in detail; the table fits many servers on one screen." },
      { path: "/monitoring/", target: ".fx-head .fx-actions .fx-btn-primary", admin: true, optional: true, title: "Add a server", body: "Administrators add servers here. Nothing needs to be typed: you get the install command, and the server fills in its own name, system, hardware, IP, provider and region." },
      { path: "/monitoring/", target: ".fx-card-head", optional: true, title: "Which server it is", body: "The status dot, name and IP address, then the operating system, provider, and the country and region with a flag. Most of it is detected by the agent." },
      { path: "/monitoring/", target: ".fx-grid .fx-spark", optional: true, title: "CPU, last 30 minutes", body: "A small live chart of the processor with the current percentage beside it." },
      { path: "/monitoring/", target: ".fx-grid .fx-meters", optional: true, title: "Memory and disk", body: "How full they are right now. The bars change colour as they fill up, so a problem stands out before an alert fires." },
      { path: "/monitoring/", target: ".fx-grid .fx-card-foot", optional: true, title: "Network, load and uptime", body: "Incoming traffic, the load average, and how long the server has been running. An offline server shows when it last reported instead." },
      { path: "/monitoring/", target: ".fx-alert-line", optional: true, title: "An alert on a card", body: "When something is wrong, the card shows it in red with the ticket Helply opened for it. Click the ticket number to go straight there." },
      { path: "/monitoring/", target: ".fx-grid .fx-pending", optional: true, title: "A new server", body: "Until the first report arrives, the card shows the setup steps and, for administrators, a Continue setup button." },
      { path: "/monitoring/", target: ".fx-card-link", click: true, optional: true, title: "Open a server", body: "Click a server to see everything about it." },
      { target: ".fx-hero", optional: true, title: "The server page", body: "The name and status at the top, then its purpose, provider, location, system and IP address. Click the IP to copy it." },
      { target: ".fx-hero .fx-actions", admin: true, optional: true, title: "Agent setup, alerts, edit", body: "Administrators can open the agent install command, pause alerts while they work (for 1, 4 or 24 hours, problems are still recorded but no tickets are raised), or edit the server's details." },
      { target: ".fx-banners", optional: true, title: "Open problems", body: "Anything that is wrong right now appears here, with how long it has been open and a link to its ticket. A notice also shows when alerts are paused." },
      { target: ".fx-tiles", optional: true, title: "Current readings", body: "CPU with the number of cores and model, memory used out of the total (plus swap), disk used out of the total, and network speed in and out with the totals since boot." },
      { target: ".fx-strip", optional: true, title: "System", body: "Load average over 1, 5 and 15 minutes, uptime, the number of running processes, and when the last report arrived." },
      { target: "[aria-labelledby=\"fx-perf\"]", optional: true, title: "Performance charts", body: "Four charts: CPU, memory and disk, network, and load. Use the time range buttons to look further back, hover to compare all four at the same moment, and watch for the dashed red lines that mark alert thresholds." },
      { target: "[aria-labelledby=\"fx-alerts\"]", optional: true, title: "Alert history", body: "Every past alert with when it started, how long it lasted, its peak and its ticket. Tickets are raised automatically when a server is offline for a few minutes, CPU or memory stays high, or the disk fills up." },
      { target: "[aria-labelledby=\"fx-about\"]", optional: true, title: "Details", body: "Plan, system, hostname, how critical the server is, who looks after it (or the service desk when nobody is set), the agent version, and since when it has been monitored." },
      { target: "[aria-labelledby=\"fx-cost\"]", optional: true, title: "Cost and renewal", body: "Monthly and yearly cost, the renewal date with the days left, and a link to the matching record in Assets. People are reminded before it renews." },
      { target: "[aria-labelledby=\"fx-tickets\"]", optional: true, title: "Tickets for this server", body: "Every ticket raised for this server, by Helply or by a person, with priority and status." }
    ] },
    { id: "people", title: "People", desc: "Add colleagues and set their roles.", roles: ["administrator"], steps: [
      { target: nav("/people/"), click: true, title: "Open People", body: "Click \"People\"." },
      { path: "/people/", target: "form.fx-toolbar", title: "Find a person", body: "Search by name or filter by role and department. Open a person to change their role, team or access." },
      { path: "/people/", target: "main a[href='/people/new/']", title: "Add someone", body: "New people get a one-time link to choose their own password; no one ever sees or sets it for them." }
    ] },
    { id: "sla", title: "SLA policies", desc: "How fast each priority must be answered and fixed.", roles: ["administrator"], steps: [
      { target: nav("/sla/"), click: true, title: "Open SLA policies", body: "Click \"SLA policies\"." },
      { path: "/sla/", target: "form.fx-sla", title: "Set the clock", body: "Write times like 30m, 4h or 1d 2h for each priority. The timer pauses while a ticket waits for the requester, and people are warned before a deadline is missed." }
    ] }
  ];

  function topicsForRole() { return TOPICS.filter(function (t) { return t.roles.indexOf(role) >= 0; }); }
  function find(id) { for (var i = 0; i < TOPICS.length; i++) if (TOPICS[i].id === id) return TOPICS[i]; return null; }
  /* The full tour is every lesson for this role, back to back. */
  function keep(list) { return list.filter(function (s) { return (!s.agent || isAgent) && (!s.admin || isAdmin) && (!s.tech || role === "technician") && (!s.emp || !isAgent); }); }
  function stepsFor(id) {
    /* "pick:a,b,c" is the lessons the person ticked, in the menu's order. */
    if (id.indexOf("pick:") === 0) { var ids = id.slice(5).split(","), out2 = []; topicsForRole().forEach(function (t) { if (ids.indexOf(t.id) >= 0) keep(t.steps).forEach(function (s) { out2.push(s); }); }); return out2; }
    if (id === "all") { var out = []; topicsForRole().forEach(function (t) { keep(t.steps).forEach(function (s) { out.push(s); }); }); return out; }
    var t = find(id); return t ? keep(t.steps) : [];
  }

  /* ---- state ---- */
  function save(s) { try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }
  function load() { try { var s = JSON.parse(sessionStorage.getItem(KEY) || "null"); return s && s.topic ? s : null; } catch (e) { return null; } }
  function clear() { try { sessionStorage.removeItem(KEY); } catch (e) {} }
  function here() { return location.pathname; }
  function done() { try { var d = JSON.parse(localStorage.getItem("helply-tour-done") || "{}"); return d; } catch (e) { return {}; } }
  function markDone(id) { try { var d = done(); d[id] = 1; localStorage.setItem("helply-tour-done", JSON.stringify(d)); } catch (e) {} }

  function el(tag, cls, html) { var n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  /* ---- menu ---- */
  var menu = el("div", "hp-menu"); menu.hidden = true; menu.setAttribute("role", "dialog"); menu.setAttribute("aria-label", "Help and tour");
  document.body.appendChild(menu);

  /* Ticking a lesson only selects it; nothing starts until "Start" is pressed. */
  var picked = {};
  function pickedIds() { return topicsForRole().filter(function (t) { return picked[t.id]; }).map(function (t) { return t.id; }); }
  function renderMenu(focusSel) {
    var d = done(), list = topicsForRole(), n = pickedIds().length;
    var h = '<div class="hp-menu-head"><strong>Learn Helply</strong><button type="button" class="hp-x" data-hp-close aria-label="Close help">&times;</button></div>' +
      '<p class="hp-sub">Short, hands-on lessons. You click through the real screens, and nothing is changed.</p>' +
      '<button type="button" class="hp-all" data-hp-start="all"><span><strong>Take the full tour</strong><small>' + list.length + ' lessons · about ' + Math.max(2, Math.round(stepsFor("all").length * 0.3)) + ' minutes</small></span><span aria-hidden="true">→</span></button>' +
      '<div class="hp-bulk"><span class="hp-count">' + (n ? n + ' selected' : 'Pick lessons below') + '</span>' +
      '<span><button type="button" data-hp-selall' + (n === list.length ? ' disabled' : '') + '>Select all</button><button type="button" data-hp-clearall' + (n ? '' : ' disabled') + '>Clear all</button></span></div>' +
      '<ul class="hp-list">';
    list.forEach(function (t) {
      var on = !!picked[t.id];
      h += '<li><button type="button" role="checkbox" aria-checked="' + on + '" data-hp-pick="' + t.id + '"><span class="hp-tick' + (on ? " is-on" : "") + '" aria-hidden="true">' + (on ? "✓" : "") + '</span><span class="hp-t"><strong>' + esc(t.title) + (t.id === currentTopic() ? ' <em class="hp-here">You are here</em>' : '') + (d[t.id] ? ' <em class="hp-done">Done</em>' : '') + '</strong><small>' + esc(t.desc) + '</small></span></button></li>';
    });
    h += '</ul><button type="button" class="hp-go" data-hp-go' + (n ? '' : ' disabled') + '>' + (n ? 'Start ' + n + (n === 1 ? ' lesson' : ' lessons') : 'Start selected lessons') + '</button>' +
      '<p class="hp-foot">Press <kbd>' + mod + '</kbd> <kbd>K</kbd> any time to search, or ask the Assistant with <kbd>' + mod + '</kbd> <kbd>J</kbd>.</p>';
    var top = menu.scrollTop;
    menu.innerHTML = h; menu.scrollTop = top;
    if (focusSel) { var f = menu.querySelector(focusSel); if (f && !f.disabled) f.focus(); }
  }
  /* The lesson for the page the person is on, so opening Help already has it ticked. */
  function currentTopic() {
    var p = location.pathname;
    if (p === "/") return "dashboard";
    if (p.indexOf("/tickets/new") === 0) return "ticket";
    var map = [["/tickets/", "tickets"], ["/kb/", "kb"], ["/assets/", "assets"], ["/monitoring/", "servers"], ["/people/", "people"], ["/sla/", "sla"]];
    for (var i = 0; i < map.length; i++) if (p.indexOf(map[i][0]) === 0) return map[i][1];
    return "";
  }
  function openMenu() { endTour(false); picked = {}; var cur = currentTopic(); if (cur && topicsForRole().some(function (t) { return t.id === cur; })) picked[cur] = true; renderMenu("[data-hp-start]"); menu.hidden = false; btn.setAttribute("aria-expanded", "true"); }
  function closeMenu() { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); }
  btn.setAttribute("aria-haspopup", "dialog"); btn.setAttribute("aria-expanded", "false");
  btn.addEventListener("click", function () { menu.hidden ? openMenu() : closeMenu(); });
  menu.addEventListener("click", function (e) {
    var s = e.target.closest("[data-hp-start]");
    if (s) { closeMenu(); start(s.getAttribute("data-hp-start")); return; }
    var p = e.target.closest("[data-hp-pick]");
    if (p) { var id = p.getAttribute("data-hp-pick"); picked[id] = !picked[id]; renderMenu('[data-hp-pick="' + id + '"]'); return; }
    if (e.target.closest("[data-hp-selall]")) { topicsForRole().forEach(function (t) { picked[t.id] = true; }); renderMenu("[data-hp-clearall]"); return; }
    if (e.target.closest("[data-hp-clearall]")) { picked = {}; renderMenu("[data-hp-selall]"); return; }
    if (e.target.closest("[data-hp-go]")) { var ids = pickedIds(); if (ids.length) { closeMenu(); start("pick:" + ids.join(",")); } return; }
    if (e.target.closest("[data-hp-close]")) { closeMenu(); btn.focus(); }
  });
  document.addEventListener("pointerdown", function (e) { if (!menu.hidden && !menu.contains(e.target) && !btn.contains(e.target)) closeMenu(); });

  /* ---- tour ---- */
  var shade = null, ring = null, card = null, active = null, clickEl = null, clickHandler = null, raf = 0;

  function ensureUi() {
    if (shade) return;
    shade = el("div", "hp-shade"); shade.setAttribute("aria-hidden", "true");
    ring = el("div", "hp-ring"); ring.setAttribute("aria-hidden", "true");
    card = el("div", "hp-card"); card.setAttribute("role", "dialog"); card.setAttribute("aria-live", "polite");
    document.body.appendChild(shade); document.body.appendChild(ring); document.body.appendChild(card);
  }

  /* The search palette and the Assistant drawer are only open while the lesson is talking about them. */
  function closePanels(keep) {
    if (keep !== "palette") { var o = document.querySelector(".tc-overlay.is-open"); if (o) o.classList.remove("is-open"); }
    if (keep !== "drawer") { var d = document.getElementById("ai-drawer"); if (d && d.classList.contains("open") && window.HelplyAssistant) window.HelplyAssistant.close(); }
  }
  function start(id) {
    var steps = stepsFor(id); if (!steps.length) return;
    active = { topic: id, i: 0 }; save(active); show();
  }
  function endTour(finished) {
    if (active) closePanels();
    if (finished && active) { if (active.topic === "all") topicsForRole().forEach(function (t) { markDone(t.id); }); else if (active.topic.indexOf("pick:") === 0) active.topic.slice(5).split(",").forEach(markDone); else markDone(active.topic); }
    active = null; clear(); detachClick();
    cancelAnimationFrame(raf);
    [shade, ring, card].forEach(function (n) { if (n) n.remove(); }); shade = ring = card = null;
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true);
  }
  function detachClick() { if (clickEl && clickHandler) clickEl.removeEventListener("click", clickHandler, true); clickEl = clickHandler = null; }

  function query(sel) { if (!sel) return null; try { var n = document.querySelector(sel); return n && n.getClientRects().length ? n : null; } catch (e) { return null; } }

  /* Steps whose page element is optional (e.g. employees may not see the Assistant panel) are skipped. */
  function currentSteps() { return stepsFor(active.topic); }
  function stepMatchesPage(s) { return !s.path || s.path === here(); }

  function show() {
    if (!active) return;
    detachClick();
    var steps = currentSteps(), s = steps[active.i];
    if (!s) { endTour(true); return; }
    ensureUi();
    closePanels(s.ui);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", place); window.addEventListener("scroll", place, true);

    var onPage = stepMatchesPage(s), target = onPage ? query(s.target) : null;
    if (onPage && !target && s.optional) { active.i++; save(active); show(); return; }
    /* A step that needs the palette/drawer open: open it for the person (it is only a view). */
    if (onPage && s.needsOpen && !target) { var prev = steps[active.i - 1]; if (prev && prev.target) { var t0 = query(prev.target); if (t0) t0.click(); } target = query(s.target); }
    s._el = target;

    var total = steps.length, n = active.i + 1;
    var topic = active.topic === "all" ? "Full tour" : active.topic.indexOf("pick:") === 0 ? "Your lessons" : (find(active.topic) || {}).title;
    var html = '<div class="hp-meta"><span>' + esc(topic) + '</span><span>' + n + ' / ' + total + '</span></div>' +
      '<h3>' + esc(s.title) + '</h3><p>' + esc(s.body) + '</p>';
    if (!onPage) html += '<p class="hp-where">This step is on another page.</p>';
    else if (s.click && target) html += '<p class="hp-do"><span aria-hidden="true">👆</span> Click the highlighted item to continue.</p>';
    html += '<div class="hp-bar"><button type="button" class="hp-ghost" data-hp-skip>Exit</button><span class="hp-sp"></span>';
    if (active.i > 0) html += '<button type="button" class="hp-ghost" data-hp-back>Back</button>';
    if (!onPage) html += '<button type="button" class="hp-primary" data-hp-go>Take me there</button>';
    else if (s.click && target) html += '<button type="button" class="hp-ghost" data-hp-next>Skip this</button>';
    else html += '<button type="button" class="hp-primary" data-hp-next>' + (n === total ? "Finish" : "Next") + '</button>';
    html += '</div>';
    card.innerHTML = html;
    card.className = "hp-card" + (target ? "" : " is-center");

    if (target && s.click) {
      clickEl = target;
      clickHandler = function () {
        /* Count the click as the step: move on before the browser follows the link. */
        active.i++; save(active);
        if (!(target.tagName === "A" && target.getAttribute("href"))) setTimeout(show, 120);
      };
      target.addEventListener("click", clickHandler, true);
    }
    if (target) { target.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }
    place();
    setTimeout(place, 350);
    var focusBtn = card.querySelector(".hp-primary") || card.querySelector("[data-hp-next]"); if (focusBtn) focusBtn.focus({ preventScroll: true });
  }

  function place() {
    if (!active || !card) return;
    var s = currentSteps()[active.i]; var t = s && s._el;
    var vw = window.innerWidth, vh = window.innerHeight;
    if (!t || !document.contains(t)) {
      ring.style.opacity = "0"; shade.classList.add("is-solid");
      card.style.left = card.style.top = ""; return;
    }
    shade.classList.remove("is-solid");
    var r = t.getBoundingClientRect(), pad = 6;
    ring.style.opacity = "1";
    ring.style.left = (r.left - pad) + "px"; ring.style.top = (r.top - pad) + "px";
    ring.style.width = (r.width + pad * 2) + "px"; ring.style.height = (r.height + pad * 2) + "px";
    /* Card goes beside the target when there's room, below/above otherwise; always on screen. */
    var cw = card.offsetWidth, ch = card.offsetHeight, gap = 14, x, y;
    if (vw > 700 && r.right + gap + cw < vw - 8) { x = r.right + gap; y = r.top + r.height / 2 - ch / 2; }
    else if (r.bottom + gap + ch < vh - 8) { x = r.left + r.width / 2 - cw / 2; y = r.bottom + gap; }
    else if (r.top - gap - ch > 8) { x = r.left + r.width / 2 - cw / 2; y = r.top - gap - ch; }
    else { x = vw / 2 - cw / 2; y = vh - ch - 12; }
    x = Math.max(8, Math.min(x, vw - cw - 8)); y = Math.max(8, Math.min(y, vh - ch - 8));
    card.style.left = x + "px"; card.style.top = y + "px";
  }

  function go(delta) {
    if (!active) return;
    var steps = currentSteps(), next = active.i + delta;
    if (next < 0) return;
    if (next >= steps.length) { endTour(true); return; }
    active.i = next; save(active);
    var s = steps[next];
    if (s.path && s.path !== here()) { location.href = s.path; return; }
    show();
  }
  function onKey(e) {
    if (!active) return;
    if (e.key === "Escape") { e.stopPropagation(); endTour(false); }
    else if (e.key === "ArrowRight" && !(currentSteps()[active.i] || {}).click) go(1);
    else if (e.key === "ArrowLeft") go(-1);
  }
  document.addEventListener("click", function (e) {
    if (!card || !card.contains(e.target)) return;
    if (e.target.closest("[data-hp-next]")) go(1);
    else if (e.target.closest("[data-hp-back]")) go(-1);
    else if (e.target.closest("[data-hp-skip]")) endTour(false);
    else if (e.target.closest("[data-hp-go]")) { var s = currentSteps()[active.i]; if (s && s.path) location.href = s.path; }
  });

  /* Resume after a page load. */
  var saved = load();
  if (saved && (saved.topic === "all" || find(saved.topic)) && !(find(saved.topic) && find(saved.topic).roles.indexOf(role) < 0)) {
    active = saved;
    var go0 = function () { show(); };
    if (document.readyState === "complete") setTimeout(go0, 250); else window.addEventListener("load", function () { setTimeout(go0, 250); });
  } else if (saved) clear();

  window.HelplyHelp = { open: openMenu, start: start };
})();
