/**
 * AI Daily 聚合页：按月 / 分类 / 标签 / 未读
 * 路由 hash: #/2026-05 | #/2026-05/day/2026-05-28 | #/2026-05/tag/anthropic | #/2026-05/cat/cat:model
 */
(function () {
  const STORAGE_KEY = "ai-daily-state-v2";

  const BASE = (() => {
    if (location.pathname.includes("/cursor/")) return "/cursor/";
    const meta = document.querySelector('meta[name="base-path"]')?.content;
    if (meta) return meta.endsWith("/") ? meta : meta + "/";
    return "/ai-daily/";
  })();

  let manifest = null;
  let monthData = null;
  let lang = localStorage.getItem("ai-daily-lang") || "zh";
  let route = { month: "", view: "hub", date: "", tag: "", cat: "" };
  let filterUnread = false;

  function asset(path) {
    return BASE + path.replace(/^\//, "");
  }

  async function fetchJSON(path) {
    const res = await fetch(asset(path));
    if (!res.ok) throw new Error(path + " " + res.status);
    return res.json();
  }

  function loadState() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function saveState(s) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  }

  function itemKey(date, id) {
    return date + ":" + id;
  }

  function isRead(date, id) {
    return !!loadState().read?.[itemKey(date, id)];
  }

  function markRead(date, id) {
    const s = loadState();
    s.read = s.read || {};
    s.read[itemKey(date, id)] = Date.now();
    saveState(s);
  }

  function markDayRead(date) {
    if (!monthData) return;
    monthData.items.filter((it) => it.date === date).forEach((it) => markRead(date, it.id));
    render();
  }

  function markAllVisibleRead() {
    getVisibleItems().forEach((it) => markRead(it.date, it.id));
    render();
  }

  function getLastVisit() {
    return loadState().lastVisit || "";
  }

  function setLastVisit() {
    const s = loadState();
    s.lastVisit = manifest?.latest_date || new Date().toISOString().slice(0, 10);
    s.lastVisitAt = Date.now();
    saveState(s);
  }

  function isUnreadItem(it) {
    if (isRead(it.date, it.id)) return false;
    const lv = getLastVisit();
    if (!lv) return true;
    return it.date >= lv;
  }

  function parseRoute() {
    const h = (location.hash || "").replace(/^#\/?/, "");
    const parts = h.split("/").filter(Boolean);
    route = { month: "", view: "hub", date: "", tag: "", cat: "" };
    if (!parts.length) {
      route.month = manifest?.months?.[0]?.id || manifest?.days?.[0]?.month || "";
      return;
    }
    route.month = parts[0];
    if (parts[1] === "day" && parts[2]) {
      route.view = "day";
      route.date = parts[2];
    } else if (parts[1] === "tag" && parts[2]) {
      route.view = "tag";
      route.tag = decodeURIComponent(parts[2]);
    } else if (parts[1] === "cat" && parts[2]) {
      route.view = "cat";
      route.cat = decodeURIComponent(parts[2]);
    } else {
      route.view = "hub";
    }
  }

  function navigate(hash) {
    location.hash = hash;
  }

  function t(zh, en) {
    return lang === "zh" ? zh : en;
  }

  function displayTitle(it) {
    if (lang === "en") return it.title?.en || it.title?.zh || "";
    return it.title?.zh || it.title?.en || "";
  }

  function displaySummary(it) {
    if (lang === "en") return it.summary?.en || "";
    return it.summary?.zh || "";
  }

  function displayEnSubtle(it) {
    if (lang !== "zh") return "";
    const en = (it.title?.en || "").trim();
    const zh = (it.title?.zh || "").trim();
    if (!en || en === zh) return "";
    return en;
  }

  function entityTags(it) {
    return it.entity_tags || (it.tags || []).filter((x) => !String(x).startsWith("cat:"));
  }

  function getVisibleItems() {
    if (!monthData) return [];
    let list = [...monthData.items];
    if (route.view === "day") list = list.filter((it) => it.date === route.date);
    else if (route.view === "tag") {
      const keys = new Set(monthData.tag_index?.[route.tag] || []);
      list = list.filter((it) => keys.has(itemKey(it.date, it.id)));
    } else if (route.view === "cat") {
      const keys = new Set(monthData.category_index?.[route.cat] || []);
      list = list.filter((it) => keys.has(itemKey(it.date, it.id)));
    }
    if (filterUnread) list = list.filter(isUnreadItem);
    return list;
  }

  function countUnreadForMonth() {
    if (!monthData) return 0;
    return monthData.items.filter(isUnreadItem).length;
  }

  function countUnreadByTag(tag) {
    const keys = monthData?.tag_index?.[tag] || [];
    return keys.filter((k) => {
      const [d, id] = k.split(":");
      return !isRead(d, id);
    }).length;
  }

  function countUnreadByCat(cat) {
    const keys = monthData?.category_index?.[cat] || [];
    return keys.filter((k) => {
      const [d, id] = k.split(":");
      return !isRead(d, id);
    }).length;
  }

  function countUnreadByDay(date) {
    return monthData.items.filter((it) => it.date === date && isUnreadItem(it)).length;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderCard(it) {
    const title = displayTitle(it);
    const summary = displaySummary(it);
    const subtle = displayEnSubtle(it);
    const unread = isUnreadItem(it);
    const tags = entityTags(it)
      .map(
        (tag) =>
          `<button type="button" class="tag-chip" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`
      )
      .join("");
    return `<a class="blog-card${unread ? " unread" : ""}" href="${escapeHtml(it.url)}" target="_blank" rel="noopener noreferrer" data-date="${it.date}" data-id="${it.id}">
      <h4>${escapeHtml(title)}</h4>
      ${subtle ? `<p class="en-subtle">${escapeHtml(subtle)}</p>` : ""}
      ${summary ? `<p class="summary">${escapeHtml(summary)}</p>` : ""}
      <div class="card-footer">
        <span>${escapeHtml(it.source)} · ${it.date}</span>
        ${tags}
        <button type="button" class="mark-read-btn" data-mark="${it.date}:${it.id}">${t("标为已读", "Mark read")}</button>
      </div>
    </a>`;
  }

  function renderMain() {
    const el = document.getElementById("main-panel");
    const items = getVisibleItems();
    const unreadTotal = countUnreadForMonth();
    const lv = getLastVisit();

    let title = "";
    let extra = "";

    if (route.view === "hub") {
      title = t(`${route.month} 概览`, `${route.month} Overview`);
      extra = `<div class="dashboard-card">
        <h2>${t("阅读面板", "Reading dashboard")}</h2>
        <div class="stat-row">
          <span>${t("本月", "This month")} <strong>${monthData?.item_count || 0}</strong> ${t("条", "items")}</span>
          <span>${t("未读", "Unread")} <strong>${unreadTotal}</strong></span>
          <span>${t("上次访问基准日", "Since visit")}: <strong>${lv || t("首次", "First visit")}</strong></span>
          <span>${t("最新简报", "Latest")}: <strong>${manifest?.latest_date || "-"}</strong></span>
        </div>
      </div>`;
      const byCat = manifest.categories || [];
      let body = "";
      for (const cat of byCat) {
        const catItems = items.filter((it) => it.category_tag === cat.id);
        if (!catItems.length && filterUnread) continue;
        const show = filterUnread ? catItems.filter(isUnreadItem) : catItems;
        if (!show.length) continue;
        body += `<section class="category-block" id="sec-${cat.id}"><h3>${cat.emoji} ${lang === "zh" ? cat.zh : cat.en}</h3><div class="blog-list">${show.map(renderCard).join("")}</div></section>`;
      }
      if (!body) body = `<div class="empty">${t("本月暂无匹配内容", "No items this month")}</div>`;
      el.innerHTML = extra + `<div class="toolbar">
        <button type="button" class="chip${filterUnread ? " active" : ""}" id="btn-unread-filter">${t("仅未读", "Unread only")}</button>
        <button type="button" class="chip" id="btn-mark-all">${t("全部标为已读", "Mark all read")}</button>
        <button type="button" class="chip" id="btn-catch-up">${t("追平至最新日", "Catch up to latest")}</button>
      </div>` + body;
      return;
    }

    if (route.view === "day") {
      title = t(`日报 ${route.date}`, `Daily ${route.date}`);
    } else if (route.view === "tag") {
      title = t(`标签 ${route.tag}`, `Tag ${route.tag}`);
    } else if (route.view === "cat") {
      const cat = manifest.categories.find((c) => c.id === route.cat);
      title = cat ? (lang === "zh" ? cat.zh : cat.en) : route.cat;
    }

    const list = items.length ? items.map(renderCard).join("") : `<div class="empty">${t("无内容", "Empty")}</div>`;
    el.innerHTML = `<h2 class="view-title">${escapeHtml(title)}</h2>
      <div class="toolbar">
        <button type="button" class="chip" id="btn-back-hub">${t("← 本月概览", "← Month hub")}</button>
        <button type="button" class="chip${filterUnread ? " active" : ""}" id="btn-unread-filter">${t("仅未读", "Unread only")}</button>
        ${route.view === "day" ? `<button type="button" class="chip" id="btn-mark-day">${t("本日全部已读", "Mark day read")}</button>` : ""}
      </div>
      <div class="blog-list">${list}</div>`;
  }

  function renderLeftNav() {
    const el = document.getElementById("left-nav");
    let html = `<p class="panel-title">${t("月份", "Months")}</p>`;
    for (const m of manifest.months || []) {
      const open = m.id === route.month ? " open" : "";
      const days = (monthData?.days || []).filter((d) => d.date.startsWith(m.id));
      html += `<div class="month-group"><div class="month-title${open}" data-month-toggle="${m.id}">
        <span>${lang === "zh" ? m.label_zh : m.label_en}</span><span class="icon">▶</span></div><div class="month-days${open}">`;
      for (const d of days.sort((a, b) => b.date.localeCompare(a.date))) {
        const u = countUnreadByDay(d.date);
        const active = route.view === "day" && route.date === d.date ? " active" : "";
        html += `<button type="button" class="nav-item${active}" data-day="${d.date}">
          <span>${d.date.slice(5)}</span>${u ? `<span class="badge">${u}</span>` : ""}</button>`;
      }
      html += `</div></div>`;
    }

    html += `<p class="panel-title">${t("分类", "Categories")}</p><div class="nav-stack">`;
    for (const cat of manifest.categories || []) {
      const u = countUnreadByCat(cat.id);
      const active = route.view === "cat" && route.cat === cat.id ? " active" : "";
      html += `<button type="button" class="nav-item${active}" data-cat="${cat.id}">
        <span>${cat.emoji} ${lang === "zh" ? cat.zh : cat.en}</span>${u ? `<span class="badge">${u}</span>` : `<span class="badge muted">0</span>`}</button>`;
    }
    html += `</div>`;
    el.innerHTML = html;
  }

  function renderTagPanel() {
    const el = document.getElementById("tag-panel");
    const stats = monthData?.tag_stats || [];
    let html = `<p class="panel-title">${t("本月标签", "Tags this month")}</p><div class="tag-cloud">`;
    for (const { tag, count } of stats.slice(0, 40)) {
      const u = countUnreadByTag(tag);
      const active = route.view === "tag" && route.tag === tag ? " active" : "";
      html += `<button type="button" class="chip${active}" data-tag-nav="${escapeHtml(tag)}">${escapeHtml(tag)} <span class="badge${u ? "" : " muted"}">${u || count}</span></button>`;
    }
    html += `</div>`;
    el.innerHTML = html;
  }

  function bindEvents() {
    document.getElementById("btn-en")?.addEventListener("click", () => switchLang("en"));
    document.getElementById("btn-zh")?.addEventListener("click", () => switchLang("zh"));

    document.getElementById("left-nav")?.addEventListener("click", (e) => {
      const mt = e.target.closest("[data-month-toggle]");
      if (mt) {
        navigate("#/" + mt.dataset.monthToggle);
        return;
      }
      const day = e.target.closest("[data-day]");
      if (day) {
        navigate(`#/${route.month}/day/${day.dataset.day}`);
        return;
      }
      const cat = e.target.closest("[data-cat]");
      if (cat) {
        navigate(`#/${route.month}/cat/${encodeURIComponent(cat.dataset.cat)}`);
      }
    });

    document.getElementById("tag-panel")?.addEventListener("click", (e) => {
      const tag = e.target.closest("[data-tag-nav]");
      if (tag) navigate(`#/${route.month}/tag/${encodeURIComponent(tag.dataset.tagNav)}`);
    });

    document.getElementById("main-panel")?.addEventListener("click", (e) => {
      if (e.target.id === "btn-unread-filter") {
        filterUnread = !filterUnread;
        render();
        return;
      }
      if (e.target.id === "btn-mark-all") {
        markAllVisibleRead();
        return;
      }
      if (e.target.id === "btn-catch-up") {
        setLastVisit();
        render();
        return;
      }
      if (e.target.id === "btn-mark-day") {
        markDayRead(route.date);
        return;
      }
      if (e.target.id === "btn-back-hub") {
        navigate("#/" + route.month);
        return;
      }
      const mark = e.target.closest("[data-mark]");
      if (mark) {
        e.preventDefault();
        e.stopPropagation();
        const [d, id] = mark.dataset.mark.split(":");
        markRead(d, id);
        render();
        return;
      }
      const tagChip = e.target.closest(".tag-chip");
      if (tagChip) {
        e.preventDefault();
        e.stopPropagation();
        navigate(`#/${route.month}/tag/${encodeURIComponent(tagChip.dataset.tag)}`);
        return;
      }
      const card = e.target.closest(".blog-card");
      if (card?.dataset.date) {
        markRead(card.dataset.date, card.dataset.id);
      }
    });
  }

  function switchLang(next) {
    lang = next;
    localStorage.setItem("ai-daily-lang", lang);
    document.getElementById("btn-en")?.classList.toggle("active", lang === "en");
    document.getElementById("btn-zh")?.classList.toggle("active", lang === "zh");
    document.getElementById("page-title").textContent = lang === "zh" ? "AI 简报" : "AI Daily";
    document.getElementById("page-desc").textContent =
      lang === "zh"
        ? "按月份、分类与标签浏览精选 AI 资讯；未读高亮。"
        : "Browse curated AI news by month, category and tags.";
    render();
  }

  async function loadMonth(month) {
    monthData = await fetchJSON("data/monthly/" + month + ".json");
  }

  async function render() {
    parseRoute();
    if (!route.month && manifest?.months?.length) route.month = manifest.months[0].id;
    if (route.month) await loadMonth(route.month);
    renderLeftNav();
    renderTagPanel();
    renderMain();
  }

  async function init() {
    bindEvents();
    switchLang(lang);
    try {
      manifest = await fetchJSON("data/manifest.json");
      if (!location.hash) navigate("#/" + (manifest.months?.[0]?.id || ""));
      await render();
      window.addEventListener("hashchange", () => render());
    } catch (err) {
      document.getElementById("main-panel").innerHTML =
        `<div class="empty">Failed to load: ${escapeHtml(err.message)}</div>`;
    }
  }

  init();
})();
