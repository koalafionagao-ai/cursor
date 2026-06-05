/**
 * AI Daily 聚合页 v2：统计口径统一、标签分组、已读状态可见
 */
(function () {
  const STORAGE_KEY = "ai-daily-state-v2";

  const BASE = (() => {
    const meta = document.querySelector('meta[name="base-path"]')?.content;
    if (meta) return meta.endsWith("/") ? meta : meta + "/";
    const path = location.pathname || "";
    if (path.includes("/ai_daily")) return "/cursor/ai_daily/";
    return "/cursor/ai_daily/";
  })();

  let manifest = null;
  let monthData = null;
  let monthStats = null;
  let lang = localStorage.getItem("ai-daily-lang") || "zh";
  let route = { month: "", view: "hub", date: "", tag: "", cat: "" };
  /** 主面板默认只看未读；关闭后显示全部（已读带 ✅） */
  let filterUnread = true;
  const monthCache = {};
  let expandedYears = new Set();
  let expandedMonths = new Set();
  const UI_STATE_KEY = "ai-daily-ui-v3";

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
    return `${date}:${id}`;
  }

  function findItem(date, id) {
    return monthData?.items?.find((it) => it.date === date && it.id === id);
  }

  function findItemByKey(key) {
    const [date, id] = key.split(":");
    return findItem(date, id);
  }

  function isExplicitlyRead(date, id) {
    return !!loadState().read?.[itemKey(date, id)];
  }

  function markRead(date, id) {
    const s = loadState();
    s.read = s.read || {};
    s.read[itemKey(date, id)] = Date.now();
    saveState(s);
  }

  function findCardByMark(date, id) {
    const key = `${date}:${id}`;
    for (const btn of document.querySelectorAll("[data-mark]")) {
      if (btn.dataset.mark === key) return btn.closest(".blog-card");
    }
    return null;
  }

  function toggleItemReadState(date, id) {
    if (isExplicitlyRead(date, id)) {
      const s = loadState();
      delete s.read?.[itemKey(date, id)];
      saveState(s);
    } else {
      markRead(date, id);
    }

    monthStats = computeMonthStats();
    updateMobileTopNav();
    renderLeftNav();
    renderTagPanel();
    syncMobileFilterPanel();

    const card = findCardByMark(date, id);
    const feed = document.querySelector(".main-feed-scroll");
    const scrollY = feed ? feed.scrollTop : 0;
    const nowRead = isExplicitlyRead(date, id);

    if (filterUnread && nowRead && card && feed) {
      const cardHeight = card.offsetHeight;
      const cardTop = card.getBoundingClientRect().top - feed.getBoundingClientRect().top + feed.scrollTop;
      card.remove();
      document.querySelectorAll(".category-block").forEach((sec) => {
        if (!sec.querySelector(".blog-card")) sec.remove();
      });
      if (feed && scrollY > cardTop) {
        feed.scrollTop = Math.max(0, scrollY - cardHeight - 18);
      }
      return;
    }

    if (!card) return;

    card.classList.toggle("unread", !nowRead);
    card.classList.toggle("is-read", nowRead);
    const btn = card.querySelector(".mark-read-btn");
    if (btn) {
      btn.textContent = nowRead ? t("标为未读", "Mark unread") : t("标为已读", "Mark read");
    }
    let badge = card.querySelector(".read-badge");
    if (nowRead && !badge) {
      badge = document.createElement("span");
      badge.className = "read-badge";
      badge.setAttribute("aria-label", "read");
      badge.textContent = "✓";
      card.insertBefore(badge, card.firstChild);
    } else if (!nowRead && badge) {
      badge.remove();
    }

    if (feed) feed.scrollTop = scrollY;
  }

  function syncMobileHeaderHeight() {
    if (!isMobileViewport()) return;
    const header = document.querySelector(".header-bar");
    if (!header) return;
    document.documentElement.style.setProperty("--m-header-h", `${header.offsetHeight}px`);
  }

  function markAllVisibleRead() {
    getVisibleItems(false).forEach((it) => markRead(it.date, it.id));
    render();
  }

  function resetReadState() {
    if (confirm(t("确定清空本机阅读记录？", "Clear all read state on this device?"))) {
      localStorage.removeItem(STORAGE_KEY);
      render();
    }
  }

  function getCurrentScopeItems() {
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
    return list;
  }

  function resetCurrentToUnread() {
    if (
      !confirm(
        t(
          "确定将当前范围全部重置为未读？",
          "Reset everything in the current view to unread?"
        )
      )
    ) {
      return;
    }
    const s = loadState();
    s.read = s.read || {};
    for (const it of getCurrentScopeItems()) {
      delete s.read[itemKey(it.date, it.id)];
    }
    saveState(s);
    render();
  }

  function closeOperateMenu() {
    const menu = document.getElementById("toolbar-operate-menu");
    if (menu) menu.hidden = true;
  }

  /** 未读 = 未在本机标为已读 */
  function isUnreadItem(it) {
    return !isExplicitlyRead(it.date, it.id);
  }

  function computeMonthStats() {
    const items = monthData?.items || [];
    const unreadList = items.filter(isUnreadItem);
    const readCount = items.length - unreadList.length;

    const byDay = {};
    const byCat = {};
    const byTag = {};

    for (const it of items) {
      const u = isUnreadItem(it);
      if (!byDay[it.date]) byDay[it.date] = { total: 0, unread: 0 };
      byDay[it.date].total += 1;
      if (u) byDay[it.date].unread += 1;

      const cat = it.category_tag || "cat:other";
      if (!byCat[cat]) byCat[cat] = { total: 0, unread: 0 };
      byCat[cat].total += 1;
      if (u) byCat[cat].unread += 1;

      for (const tag of entityTags(it)) {
        if (!byTag[tag]) byTag[tag] = { total: 0, unread: 0 };
        byTag[tag].total += 1;
        if (u) byTag[tag].unread += 1;
      }
    }

    return {
      total: items.length,
      unread: unreadList.length,
      read: readCount,
      byDay,
      byCat,
      byTag,
      daysWithUnread: Object.keys(byDay).filter((d) => byDay[d].unread > 0).length,
      catsWithUnread: Object.values(byCat).filter((c) => c.unread > 0).length,
      tagsWithUnread: Object.values(byTag).filter((t) => t.unread > 0).length,
    };
  }

  function parseRoute() {
    const h = (location.hash || "").replace(/^#\/?/, "");
    const parts = h.split("/").filter(Boolean);
    route = { month: "", view: "hub", date: "", tag: "", cat: "" };
    if (!parts.length) {
      route.month = manifest?.months?.[0]?.id || "";
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

  function entityTags(it) {
    return it.entity_tags || (it.tags || []).filter((x) => !String(x).startsWith("cat:"));
  }

  function displayTitle(it) {
    if (lang === "en") return it.title?.en || it.title?.zh || "";
    return it.title?.zh || it.title?.en || "";
  }

  function displaySummary(it) {
    if (lang === "en") return it.summary?.en || "";
    return it.summary?.zh || "";
  }

  function displayEnSecondary(it) {
    if (lang !== "zh") return "";
    const en = (it.title?.en || "").trim();
    const zh = (it.title?.zh || "").trim();
    if (!en || en === zh) return "";
    return en;
  }

  function countLabel(unread, total) {
    if (total === 0) return "";
    return `${unread}/${total}`;
  }



  function persistUiState() {
    sessionStorage.setItem(
      UI_STATE_KEY,
      JSON.stringify({
        expandedYears: [...expandedYears],
        expandedMonths: [...expandedMonths],
      })
    );
  }

  function initExpandState() {
    const months = manifest?.months || [];
    if (!months.length) return;
    const latestMonth = months[0].id;
    const latestYear = latestMonth.slice(0, 4);
    try {
      const saved = JSON.parse(sessionStorage.getItem(UI_STATE_KEY) || "{}");
      const savedYears = saved.expandedYears || [];
      const savedMonths = saved.expandedMonths || [];
      if (savedYears.length && !savedYears.includes(latestYear)) {
        expandedYears = new Set([latestYear]);
        expandedMonths = new Set([latestMonth]);
      } else if (savedMonths.length && !savedMonths.includes(latestMonth)) {
        const newestSaved = savedMonths.reduce((a, b) => (a > b ? a : b), "");
        if (latestMonth > newestSaved) {
          expandedYears = new Set(savedYears.length ? savedYears : [latestYear]);
          expandedMonths = new Set([latestMonth]);
        } else {
          expandedYears = new Set(savedYears.length ? savedYears : [latestYear]);
          expandedMonths = new Set(savedMonths.length ? savedMonths : [latestMonth]);
        }
      } else {
        expandedYears = new Set(savedYears.length ? savedYears : [latestYear]);
        expandedMonths = new Set(savedMonths.length ? savedMonths : [latestMonth]);
      }
    } catch {
      expandedYears = new Set([latestYear]);
      expandedMonths = new Set([latestMonth]);
    }
    if (route.month) {
      expandedYears.add(route.month.slice(0, 4));
      expandedMonths.add(route.month);
    }
    persistUiState();
  }

  function toggleYear(year) {
    if (expandedYears.has(year)) expandedYears.delete(year);
    else expandedYears.add(year);
    persistUiState();
  }

  function toggleMonth(monthId) {
    if (expandedMonths.has(monthId)) expandedMonths.delete(monthId);
    else expandedMonths.add(monthId);
    persistUiState();
  }

  async function prefetchMonth(monthId) {
    if (monthCache[monthId]) return monthCache[monthId];
    try {
      monthCache[monthId] = await fetchJSON(`data/monthly/${monthId}.json`);
    } catch {
      monthCache[monthId] = null;
    }
    return monthCache[monthId];
  }

  function dayStatsForMonth(monthId) {
    const data = monthId === route.month && monthData ? monthData : monthCache[monthId];
    if (!data?.items) return {};
    const byDay = {};
    for (const it of data.items) {
      if (!byDay[it.date]) byDay[it.date] = { total: 0, unread: 0 };
      byDay[it.date].total += 1;
      if (isUnreadItem(it)) byDay[it.date].unread += 1;
    }
    return byDay;
  }

  function manifestDaysForMonth(monthId) {
    return (manifest?.days || []).filter((d) => d.date.startsWith(monthId + "-"));
  }

  function monthLabelFor(routeMonth) {
    return routeMonth || "";
  }

  function monthDisplayLabel(monthId) {
    if (!monthId) return "";
    const n = parseInt(monthId.slice(5, 7), 10);
    if (lang === "zh") return `${n}月`;
    const en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return en[n - 1] || monthId.slice(5, 7);
  }

  function renderFilterChips() {
    return `<div class="toolbar-filters">
      <button type="button" class="chip chip-filter${filterUnread ? " active" : ""}" id="btn-filter-unread">${t("未读", "Unread")}</button>
      <button type="button" class="chip chip-filter${!filterUnread ? " active" : ""}" id="btn-filter-all">${t("全部", "All")}</button>
    </div>`;
  }

  function renderActionChips() {
    return `<div class="toolbar-actions">
      <button type="button" class="chip chip-act" id="btn-mark-all">${t("当前全部已读", "Mark all read")}</button>
      <button type="button" class="chip chip-act chip-ghost" id="btn-reset-unread">${t("当前重置为未读", "Reset to unread")}</button>
    </div>`;
  }

  function renderMobileOperateMenu() {
    return `<div class="toolbar-operate-wrap">
      <button type="button" class="chip chip-act chip-operate" id="btn-operate-toggle" aria-expanded="false">${t("操作", "Actions")}</button>
      <div class="toolbar-operate-menu" id="toolbar-operate-menu" hidden>
        <button type="button" class="chip chip-act" id="btn-mark-all">${t("当前全部已读", "Mark all read")}</button>
        <button type="button" class="chip chip-act chip-ghost" id="btn-reset-unread">${t("当前重置为未读", "Reset to unread")}</button>
      </div>
    </div>`;
  }

  function renderToolbar(opts = {}) {
    const { showActions = true } = opts;
    const filters = renderFilterChips();
    if (!showActions) return `<div class="toolbar">${filters}</div>`;
    if (isMobileViewport()) {
      return `<div class="toolbar toolbar--mobile">${filters}${renderMobileOperateMenu()}</div>`;
    }
    return `<div class="toolbar">${filters}${renderActionChips()}</div>`;
  }

  function renderMobileFeedFooter() {
    return `<footer class="mobile-feed-footer" aria-label="Site footer">
      <p>© 2026 Fiona Gao · AI Daily · <a href="https://github.com/koalafionagao-ai" target="_blank" rel="noopener noreferrer">GitHub</a></p>
    </footer>`;
  }

  function syncMobileHeaderToolbar(html) {
    const slot = document.getElementById("mobile-header-toolbar");
    if (!slot) return;
    if (!isMobileViewport()) {
      slot.hidden = true;
      slot.innerHTML = "";
      return;
    }
    slot.hidden = false;
    slot.innerHTML = html || "";
  }

  function wrapMainScrollable(headHtml, toolbarHtml, bodyHtml) {
    if (isMobileViewport()) {
      if (headHtml) syncMobileHubPanel(headHtml);
      syncMobileHeaderToolbar(toolbarHtml);
      return `<div class="main-column">
      <div class="main-feed-scroll">${bodyHtml}${renderMobileFeedFooter()}</div>
    </div>`;
    }
    return `<div class="main-column">
      <div class="main-toolbar-wrap">${toolbarHtml}</div>
      <div class="main-feed-scroll">
        <div class="main-hub-head">${headHtml}</div>
        ${bodyHtml}
      </div>
    </div>`;
  }

  function getVisibleItems(applyUnreadFilter = filterUnread) {
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
    if (applyUnreadFilter) list = list.filter(isUnreadItem);
    return list.sort((a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
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
    const enLine = displayEnSecondary(it);
    const unread = isUnreadItem(it);
    const read = !unread;
    const tags = entityTags(it)
      .map(
        (tag) =>
          `<button type="button" class="tag-chip" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`
      )
      .join("");

    const titleBlock =
      lang === "zh" && enLine
        ? `<div class="title-block">
            <h4 class="title-zh">${escapeHtml(title)}</h4>
            <p class="title-en" title="${escapeHtml(enLine)}">${escapeHtml(enLine)}</p>
          </div>`
        : `<h4 class="title-zh">${escapeHtml(title)}</h4>`;

    return `<a class="blog-card${unread ? " unread" : ""}${read ? " is-read" : ""}" href="${escapeHtml(it.url)}" target="_blank" rel="noopener noreferrer" data-date="${it.date}" data-id="${it.id}">
      ${read ? `<span class="read-badge" aria-label="read">✓</span>` : ""}
      ${titleBlock}
      ${summary ? `<p class="summary">${escapeHtml(summary)}</p>` : ""}
      <div class="card-footer">
        <div class="card-footer-row">
          <div class="card-meta-tags">
            <span class="meta-line">${escapeHtml(it.source)} · ${it.date}</span>
            <span class="tag-row${tags ? "" : " tag-row-empty"}">${tags || `<span class="tag-none">—</span>`}</span>
          </div>
          <button type="button" class="mark-read-btn" data-mark="${it.date}:${it.id}">${read ? t("标为未读", "Mark unread") : t("标为已读", "Mark read")}</button>
        </div>
      </div>
    </a>`;
  }

  function renderDashboard() {
    const s = monthStats;
  const ml = monthLabelFor(route.month);
  return `<div class="dashboard-card dashboard-hero">
      <div class="dash-row dash-row-top">
        <div class="dash-latest">
          <span class="dash-kicker">${t("最新简报", "Latest brief")}</span>
          <time class="dash-latest-date">${manifest?.latest_date || "-"}</time>
        </div>
      </div>
      <div class="dash-row dash-row-main">
        <div class="dash-period">
          <span class="dash-month">${escapeHtml(ml)}</span>
        </div>
        <div class="dash-unread">
          <span class="dash-unread-num">${s.unread}</span>
          <span class="dash-unread-label">${t("未读", "unread")}</span>
        </div>
      </div>
      <div class="dash-metrics">
        <div class="dash-metric"><span class="dash-metric-val">${s.total}</span><span class="dash-metric-lbl">${t("本月", "Month")}</span></div>
        <div class="dash-metric"><span class="dash-metric-val stat-unread">${s.unread}</span><span class="dash-metric-lbl">${t("未读", "Unread")}</span></div>
        <div class="dash-metric"><span class="dash-metric-val stat-read">${s.read}</span><span class="dash-metric-lbl">${t("已读", "Read")}</span></div>
        <div class="dash-metric"><span class="dash-metric-val">${s.daysWithUnread}</span><span class="dash-metric-lbl">${t("天", "Days")}</span></div>
        <div class="dash-metric"><span class="dash-metric-val">${s.catsWithUnread}</span><span class="dash-metric-lbl">${t("分类", "Cats")}</span></div>
        <div class="dash-metric"><span class="dash-metric-val">${s.tagsWithUnread}</span><span class="dash-metric-lbl">${t("标签", "Tags")}</span></div>
      </div>
    </div>`;
  }

  function renderMain() {
    const el = document.getElementById("main-panel");
    const items = getVisibleItems();
    const toolbar = renderToolbar({ showActions: true });

    if (route.view === "hub") {
      let body = "";
      if (filterUnread && items.length === 0) {
        body = `<div class="empty">${t("本月没有未读条目。可切换「显示全部」查看已读（带 ✓）。", "No unread items. Toggle “Show all” to see read items (✓).")}</div>`;
      } else {
        for (const cat of manifest.categories || []) {
          const catItems = items.filter((it) => it.category_tag === cat.id);
          if (!catItems.length) continue;
          const st = monthStats.byCat[cat.id] || { total: 0, unread: 0 };
          body += `<section class="category-block" id="sec-${cat.id}">
            <h3>${lang === "zh" ? cat.zh : cat.en}
              <span class="section-count">${countLabel(st.unread, st.total)}</span></h3>
            <div class="blog-list">${catItems.map(renderCard).join("")}</div></section>`;
        }
        if (!body) body = `<div class="empty">${t("暂无内容", "No content")}</div>`;
      }
      el.innerHTML = wrapMainScrollable(renderDashboard(), toolbar, body);
      return;
    }

    let title = "";
    if (route.view === "day") {
      const st = monthStats.byDay[route.date] || { total: 0, unread: 0 };
      title = t(`日报 ${route.date}`, `Daily ${route.date}`) + ` · ${t('共','total ')}${st.total}${t('条','')}` + (st.unread ? ` · ${st.unread}${t('未读',' unread')}` : ``);
    } else if (route.view === "tag") {
      const st = monthStats.byTag[route.tag] || { total: 0, unread: 0 };
      title = t(`标签 ${route.tag}`, `Tag ${route.tag}`) + ` · ${t('共','total ')}${st.total}${t('条','')}` + (st.unread ? ` · ${st.unread}${t('未读',' unread')}` : ``);
    } else if (route.view === "cat") {
      const cat = manifest.categories.find((c) => c.id === route.cat);
      const st = monthStats.byCat[route.cat] || { total: 0, unread: 0 };
      title = (cat ? (lang === "zh" ? cat.zh : cat.en) : route.cat) + ` · ${t('共','total ')}${st.total}${t('条','')}` + (st.unread ? ` · ${st.unread}${t('未读',' unread')}` : ``);
    }

    const list = items.length
      ? items.map(renderCard).join("")
      : `<div class="empty">${filterUnread ? t("此处无未读", "No unread here") : t("无内容", "Empty")}</div>`;
    const backLink = `<p class="view-back"><a href="#" id="link-back-hub">${t("← 返回本月面板", "← Back to month")}</a></p>`;
    const subToolbar = renderToolbar({ showActions: true });
    const head = `${backLink}<h2 class="view-title">${escapeHtml(title)}</h2>`;
    const dash = monthStats ? renderDashboard() : "";
    if (isMobileViewport() && dash) syncMobileHubPanel(dash);
    el.innerHTML = wrapMainScrollable(isMobileViewport() ? "" : dash, subToolbar, `<div class="blog-list">${list}</div>`);
  }

  function monthsByYear() {
    const map = new Map();
    for (const m of manifest?.months || []) {
      const year = m.id.slice(0, 4);
      if (!map.has(year)) map.set(year, []);
      map.get(year).push(m);
    }
    return map;
  }

  function monthNavStats(monthId) {
    if (monthId === route.month && monthStats) {
      return { unread: monthStats.unread, total: monthStats.total };
    }
    const data = monthCache[monthId];
    if (!data?.items) return null;
    let unread = 0;
    let total = 0;
    for (const it of data.items) {
      total += 1;
      if (isUnreadItem(it)) unread += 1;
    }
    return { unread, total };
  }

  function buildTimelineHtml(opts = {}) {
    const fullDates = !!opts.fullDates;
    let html = "";
    for (const [year, months] of monthsByYear()) {
      const yearOpen = expandedYears.has(year);
      html += `<div class="year-group">
        <div class="year-title${yearOpen ? " open" : ""}">
          <button type="button" class="year-label" data-month-nav="${months[0].id}">${year}</button>
          <button type="button" class="fold-btn" data-year-toggle="${year}" aria-expanded="${yearOpen}" aria-label="${t("展开/折叠年份", "Toggle year")}"><span class="fold-icon">▶</span></button>
        </div>
        <div class="year-months${yearOpen ? " open" : ""}">`;

      for (const m of months) {
        const monthOpen = expandedMonths.has(m.id);
        const isCurrent = m.id === route.month;
        const mst = monthNavStats(m.id);
        const monthUnread = mst ? mst.unread : "—";
        html += `<div class="month-group">
          <div class="month-title${monthOpen ? " open" : ""}${isCurrent ? " current" : ""}">
            <button type="button" class="month-label" data-month-nav="${m.id}">${escapeHtml(monthDisplayLabel(m.id))}</button>
            ${mst != null ? `<span class="nav-count ${monthUnread ? "" : "muted"}">${countLabel(monthUnread, mst.total)}</span>` : ""}
            <button type="button" class="fold-btn" data-month-toggle="${m.id}" aria-expanded="${monthOpen}" aria-label="${t("展开/折叠月份", "Toggle month")}"><span class="fold-icon">▶</span></button>
          </div>
          <div class="month-days${monthOpen ? " open" : ""}">`;

        if (monthOpen) {
          const days =
            m.id === route.month && monthData?.days
              ? [...monthData.days].sort((a, b) => b.date.localeCompare(a.date))
              : manifestDaysForMonth(m.id).sort((a, b) => b.date.localeCompare(a.date));
          const dayStats = dayStatsForMonth(m.id);
          for (const d of days) {
            const st = dayStats[d.date] || { total: d.total || 0, unread: 0 };
            const active = route.view === "day" && route.date === d.date ? " active" : "";
            const dayLabel = fullDates ? d.date : d.date.slice(8, 10) || d.date.slice(5);
            html += `<button type="button" class="nav-item${active}" data-day="${d.date}">
              <span>${dayLabel}</span>
              <span class="nav-count ${st.unread ? "" : "muted"}">${countLabel(st.unread, st.total)}</span>
            </button>`;
          }
          if (fullDates) {
            html += `<button type="button" class="nav-item${route.view === "hub" && route.month === m.id ? " active" : ""}" data-month-hub="${m.id}">
              <span>${t("本月全部", "All in month")}</span>
            </button>`;
          }
        }
        html += `</div></div>`;
      }
      html += `</div></div>`;
    }
    return html || `<p class="empty">${t("暂无日期", "No dates")}</p>`;
  }

  function renderLeftNav() {
    const el = document.getElementById("left-nav");
    el.innerHTML = `<p class="panel-title">${t("时间", "Timeline")}</p><div class="nav-scroll">${buildTimelineHtml()}</div>`;
  }

  function renderTagPanel() {
    const el = document.getElementById("tag-panel");
    const s = monthStats;
    const groups = window.AI_DAILY_TAG_GROUPS || [];
    const used = new Set(Object.keys(s.byTag));
    let html = `<section class="sidebar-block sidebar-cats">
      <h2 class="sidebar-block-title">${t("分类", "Categories")}<span class="sidebar-block-sub">${t("本月", "This month")}</span></h2>
      <div class="nav-stack compact-nav">`;
    for (const cat of manifest.categories || []) {
      const st = s.byCat[cat.id] || { total: 0, unread: 0 };
      if (st.total === 0) continue;
      const active = route.view === "cat" && route.cat === cat.id ? " active" : "";
      html += `<button type="button" class="nav-item${active}" data-cat="${cat.id}">
        <span>${lang === "zh" ? cat.zh : cat.en}</span>
        <span class="nav-count ${st.unread ? "" : "muted"}">${countLabel(st.unread, st.total)}</span>
      </button>`;
    }
    html += `</div></section>
      <section class="sidebar-block sidebar-tags">
      <h2 class="sidebar-block-title">${t("标签", "Tags")}<span class="sidebar-block-sub">${t("本月", "This month")}</span></h2>
      <div class="nav-scroll tags-scroll">`;

    const assigned = new Set();

    for (const group of groups) {
      const entries = [];
      for (const tag of group.tags) {
        if (!used.has(tag)) continue;
        assigned.add(tag);
        const st = s.byTag[tag];
        if (!st?.total) continue;
        entries.push({ tag, ...st });
      }
      entries.sort((a, b) => b.unread - a.unread || b.total - a.total);
      if (!entries.length) continue;

      html += `<div class="tag-group"><div class="tag-group-title">${lang === "zh" ? group.label.zh : group.label.en}</div><div class="tag-cloud">`;
      for (const { tag, unread, total } of entries) {
        const active = route.view === "tag" && route.tag === tag ? " active" : "";
        html += `<button type="button" class="chip chip-tag${active}${unread === 0 ? " is-done" : ""}" data-tag-nav="${escapeHtml(tag)}">
          <span class="tag-name">${escapeHtml(tag)}</span>
          <span class="nav-count ${unread ? "" : "muted"}">${countLabel(unread, total)}</span>
        </button>`;
      }
      html += `</div></div>`;
    }

    const other = [...used].filter((t) => !assigned.has(t)).sort();
    if (other.length) {
      html += `<div class="tag-group"><div class="tag-group-title">${t("其它", "Other")}</div><div class="tag-cloud">`;
      for (const tag of other) {
        const st = s.byTag[tag];
        const active = route.view === "tag" && route.tag === tag ? " active" : "";
        html += `<button type="button" class="chip chip-tag${active}${st.unread === 0 ? " is-done" : ""}" data-tag-nav="${escapeHtml(tag)}">
          <span class="tag-name">${escapeHtml(tag)}</span>
          <span class="nav-count ${st.unread ? "" : "muted"}">${countLabel(st.unread, st.total)}</span>
        </button>`;
      }
      html += `</div></div>`;
    }

    html += `</div></section>`;
    el.innerHTML = html;
    syncMobileFilterPanel();
  }

  const MOBILE_MQ = "(max-width: 768px)";

  function isMobileViewport() {
    return window.matchMedia(MOBILE_MQ).matches;
  }

  function mobileRouteNavPanel() {
    if (route.view === "tag" || route.view === "cat") return "filter";
    if (route.view === "day") return "date";
    return "hub";
  }

  /** 时间 tab：只显示日期/月份，不显示标签名 */
  function mobileNavTimeSub() {
    if (route.view === "day" && route.date) return route.date;
    if (route.month) {
      if (lang === "zh") return `${route.month.slice(0, 4)}年${monthDisplayLabel(route.month)}`;
      return route.month;
    }
    return manifest?.latest_date || "—";
  }

  /** 筛选 tab：标签/分类选中态 */
  function mobileNavFilterSub() {
    if (route.view === "tag" && route.tag) return route.tag;
    if (route.view === "cat" && route.cat) {
      const cat = manifest?.categories?.find((c) => c.id === route.cat);
      return cat ? (lang === "zh" ? cat.zh : cat.en) : route.cat;
    }
    return t("分类·标签", "Cats · tags");
  }

  let activeMobileNavPanel = null;

  function closeMobileSheets() {
    activeMobileNavPanel = null;
    document.getElementById("mobile-overlay")?.classList.remove("is-open");
    document.getElementById("mobile-date-sheet")?.classList.remove("is-open");
    document.getElementById("mobile-hub-sheet")?.classList.remove("is-open");
    document.getElementById("mobile-filter-drawer")?.classList.remove("is-open");
    document.body.classList.remove("mobile-sheet-open", "mobile-drawer-open");
    document.getElementById("mobile-date-sheet")?.setAttribute("aria-hidden", "true");
    document.getElementById("mobile-hub-sheet")?.setAttribute("aria-hidden", "true");
    document.getElementById("mobile-filter-drawer")?.setAttribute("aria-hidden", "true");
    document.querySelectorAll(".mobile-nav-btn").forEach((b) => {
      b.classList.remove("is-active");
      b.setAttribute("aria-expanded", "false");
    });
    updateMobileTopNav();
    const ov = document.getElementById("mobile-overlay");
    if (ov) ov.hidden = true;
  }

  function openMobileNavPanel(panel) {
    if (activeMobileNavPanel === panel) {
      closeMobileSheets();
      return;
    }
    const sheetMap = {
      date: document.getElementById("mobile-date-sheet"),
      hub: document.getElementById("mobile-hub-sheet"),
      filter: document.getElementById("mobile-filter-drawer"),
    };
    const ov = document.getElementById("mobile-overlay");
    const target = sheetMap[panel];
    if (!target || !ov) return;

    closeMobileSheets();
    activeMobileNavPanel = panel;

    if (panel === "date") {
      const titleEl = document.getElementById("mobile-date-sheet-title");
      if (titleEl) titleEl.textContent = t("选择日期", "Pick a date");
      document.getElementById("mobile-date-sheet-body").innerHTML = buildTimelineHtml({ fullDates: true });
    } else if (panel === "hub") {
      if (monthStats) syncMobileHubPanel(renderDashboard());
    } else if (panel === "filter") {
      syncMobileFilterPanel();
    }

    const btn = document.querySelector(`.mobile-nav-btn[data-nav-panel="${panel}"]`);
    btn?.classList.add("is-active");
    btn?.setAttribute("aria-expanded", "true");

    ov.hidden = false;
    requestAnimationFrame(() => {
      ov.classList.add("is-open");
      target.classList.add("is-open");
      target.setAttribute("aria-hidden", "false");
      document.body.classList.add(panel === "filter" ? "mobile-drawer-open" : "mobile-sheet-open");
    });
  }

  function syncMobileFilterPanel() {
    const src = document.getElementById("tag-panel");
    const dst = document.getElementById("mobile-filter-panel");
    if (src && dst) dst.innerHTML = src.innerHTML;
  }

  function syncMobileHubPanel(html) {
    const dst = document.getElementById("mobile-hub-panel");
    if (dst && html) dst.innerHTML = html;
  }

  function refreshOpenMobilePanelContent() {
    if (!activeMobileNavPanel || !isMobileViewport()) return;
    const panel = activeMobileNavPanel;
    if (panel === "date") {
      const titleEl = document.getElementById("mobile-date-sheet-title");
      if (titleEl) titleEl.textContent = t("选择日期", "Pick a date");
      const body = document.getElementById("mobile-date-sheet-body");
      if (body) body.innerHTML = buildTimelineHtml({ fullDates: true });
    } else if (panel === "hub" && monthStats) {
      syncMobileHubPanel(renderDashboard());
    } else if (panel === "filter") {
      syncMobileFilterPanel();
    }
  }

  function updateMobileTopNav() {
    const nav = document.getElementById("mobile-top-nav");
    if (!nav) return;
    if (!isMobileViewport()) {
      nav.hidden = true;
      return;
    }
    nav.hidden = false;

    const labelMap = {
      date: t("时间", "Time"),
      hub: t("看板", "Hub"),
      filter: t("筛选", "Filter"),
    };
    document.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
      const key = btn.dataset.navPanel;
      const labelEl = btn.querySelector(".mobile-nav-label");
      if (labelEl && labelMap[key]) labelEl.textContent = labelMap[key];
      if (labelMap[key]) btn.setAttribute("aria-label", labelMap[key]);
    });

    const filterDrawerTitle = document.querySelector("#mobile-filter-drawer .mobile-drawer-head h2");
    if (filterDrawerTitle) filterDrawerTitle.textContent = t("筛选", "Filter");

    const dateSub = document.getElementById("mobile-nav-date-sub");
    const hubSub = document.getElementById("mobile-nav-hub-sub");
    const filterSub = document.getElementById("mobile-nav-filter-sub");
    if (dateSub) dateSub.textContent = mobileNavTimeSub();
    if (filterSub) filterSub.textContent = mobileNavFilterSub();
    if (hubSub && monthStats) {
      hubSub.textContent = `${monthStats.unread} ${t("未读", "unread")}`;
    } else if (hubSub) {
      hubSub.textContent = "—";
    }
    const routePanel = mobileRouteNavPanel();
    document.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
      const isRoute = btn.dataset.navPanel === routePanel;
      btn.classList.toggle("is-route-current", isRoute);
      btn.setAttribute("aria-current", isRoute ? "page" : "false");
    });
    const hubTitle = document.getElementById("mobile-hub-sheet-title");
    if (hubTitle) hubTitle.textContent = t("本月看板", "Month dashboard");
    const dateTitle = document.getElementById("mobile-date-sheet-title");
    if (dateTitle && !activeMobileNavPanel) {
      dateTitle.textContent = t("选择日期", "Pick a date");
    }
    refreshOpenMobilePanelContent();
  }

  function updateMobileLayout(opts = {}) {
    const mobile = isMobileViewport();
    const preserveChrome = !!opts.preserveChrome;
    document.body.classList.toggle("is-mobile", mobile);
    if (!mobile) {
      closeMobileSheets();
      document.querySelector(".header-bar")?.classList.remove("header-hidden");
      document.body.classList.remove("mobile-chrome-hidden");
      syncMobileHeaderToolbar("");
      document.documentElement.style.removeProperty("--m-header-h");
    }
    updateMobileTopNav();
    syncMobileFilterPanel();
    if (monthStats) syncMobileHubPanel(renderDashboard());
    if (mobile) {
      if (!preserveChrome) {
        document.body.classList.remove("mobile-chrome-hidden");
        document.querySelector(".header-bar")?.classList.remove("header-hidden");
      }
      requestAnimationFrame(() => syncMobileHeaderHeight());
    }
  }

  async function handleTimelineClick(e) {
    const yt = e.target.closest("[data-year-toggle]");
    if (yt) {
      e.preventDefault();
      toggleYear(yt.dataset.yearToggle);
      renderLeftNav();
      if (isMobileViewport()) {
        document.getElementById("mobile-date-sheet-body").innerHTML = buildTimelineHtml({ fullDates: true });
      }
      return true;
    }
    const mt = e.target.closest("[data-month-toggle]");
    if (mt) {
      e.preventDefault();
      const monthId = mt.dataset.monthToggle;
      toggleMonth(monthId);
      if (expandedMonths.has(monthId) && monthId !== route.month) await prefetchMonth(monthId);
      renderLeftNav();
      if (isMobileViewport()) {
        document.getElementById("mobile-date-sheet-body").innerHTML = buildTimelineHtml({ fullDates: true });
      }
      return true;
    }
    const mn = e.target.closest("[data-month-nav]");
    if (mn) {
      navigate("#/" + mn.dataset.monthNav);
      closeMobileSheets();
      return true;
    }
    const hub = e.target.closest("[data-month-hub]");
    if (hub) {
      navigate("#/" + hub.dataset.monthHub);
      closeMobileSheets();
      return true;
    }
    const day = e.target.closest("[data-day]");
    if (day) {
      const monthId = day.dataset.day.slice(0, 7);
      navigate(`#/${monthId}/day/${day.dataset.day}`);
      closeMobileSheets();
      return true;
    }
    return false;
  }

  function handleFilterPanelClick(e) {
    const tag = e.target.closest("[data-tag-nav]");
    if (tag) {
      navigate(`#/${route.month}/tag/${encodeURIComponent(tag.dataset.tagNav)}`);
      closeMobileSheets();
      return true;
    }
    const cat = e.target.closest("[data-cat]");
    if (cat) {
      navigate(`#/${route.month}/cat/${encodeURIComponent(cat.dataset.cat)}`);
      closeMobileSheets();
      return true;
    }
    return false;
  }

  function bindEvents() {
    document.getElementById("btn-en")?.addEventListener("click", () => switchLang("en"));
    document.getElementById("btn-zh")?.addEventListener("click", () => switchLang("zh"));

    document.getElementById("left-nav")?.addEventListener("click", (e) => {
      handleTimelineClick(e);
    });

    document.getElementById("mobile-date-sheet-body")?.addEventListener("click", (e) => {
      handleTimelineClick(e);
    });

    document.getElementById("tag-panel")?.addEventListener("click", (e) => {
      handleFilterPanelClick(e);
    });

    document.getElementById("mobile-filter-panel")?.addEventListener("click", (e) => {
      handleFilterPanelClick(e);
    });

    document.getElementById("mobile-top-nav")?.addEventListener("click", (e) => {
      const btn = e.target.closest(".mobile-nav-btn");
      if (!btn?.dataset.navPanel) return;
      e.preventDefault();
      e.stopPropagation();
      openMobileNavPanel(btn.dataset.navPanel);
    });

    if (!document.body.dataset.mobileUiBound) {
      document.body.dataset.mobileUiBound = "1";
      document.body.addEventListener("click", (e) => {
        if (
          e.target.closest("#btn-date-sheet-close") ||
          e.target.closest("#btn-hub-sheet-close") ||
          e.target.closest("#btn-filter-drawer-close")
        ) {
          e.preventDefault();
          e.stopPropagation();
          closeMobileSheets();
          return;
        }
        if (e.target.id === "mobile-overlay" || e.target.closest("#mobile-overlay")) {
          closeMobileSheets();
        }
        if (!e.target.closest(".toolbar-operate-wrap")) {
          closeOperateMenu();
        }
      });
      window.addEventListener("resize", () => {
        syncMobileHeaderHeight();
        updateMobileLayout();
      });
    }

    const handleToolbarAction = (e) => {
      if (e.target.id === "btn-filter-unread") {
        filterUnread = true;
        render();
        return true;
      }
      if (e.target.id === "btn-filter-all") {
        filterUnread = false;
        render();
        return true;
      }
      if (e.target.id === "btn-operate-toggle") {
        e.preventDefault();
        const menu = document.getElementById("toolbar-operate-menu");
        const btn = document.getElementById("btn-operate-toggle");
        if (menu) {
          menu.hidden = !menu.hidden;
          if (btn) btn.setAttribute("aria-expanded", menu.hidden ? "false" : "true");
        }
        return true;
      }
      if (e.target.id === "btn-mark-all") {
        closeOperateMenu();
        markAllVisibleRead();
        return true;
      }
      if (e.target.id === "btn-reset-unread") {
        closeOperateMenu();
        resetCurrentToUnread();
        return true;
      }
      return false;
    };

    document.getElementById("mobile-header-toolbar")?.addEventListener("click", (e) => {
      handleToolbarAction(e);
    });

    document.getElementById("main-panel")?.addEventListener("click", (e) => {
      if (handleToolbarAction(e)) return;
      if (e.target.id === "btn-back-hub" || e.target.id === "link-back-hub") {
        e.preventDefault();
        navigate("#/" + route.month);
        return;
      }
      const mark = e.target.closest("[data-mark]");
      if (mark) {
        e.preventDefault();
        e.stopPropagation();
        const [d, id] = mark.dataset.mark.split(":");
        toggleItemReadState(d, id);
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
      if (card?.dataset.date && !e.target.closest(".mark-read-btn")) {
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
    render();
  }

  async function loadMonth(month) {
    monthData = await fetchJSON("data/monthly/" + month + ".json");
    monthStats = computeMonthStats();
  }

  async function render(opts = {}) {
    const feed = document.querySelector(".main-feed-scroll");
    const scrollY = opts.preserveScroll && feed ? feed.scrollTop : null;
    const preserveChrome =
      opts.preserveScroll && document.body.classList.contains("mobile-chrome-hidden");
    parseRoute();
    if (!route.month && manifest?.months?.length) route.month = manifest.months[0].id;
    initExpandState();
    if (route.month) await loadMonth(route.month);
    for (const monthId of expandedMonths) {
      if (monthId !== route.month) await prefetchMonth(monthId);
    }
    renderLeftNav();
    renderTagPanel();
    renderMain();
    updateMobileLayout({ preserveChrome });
    bindMobileChrome();
    if (scrollY != null) {
      const newFeed = document.querySelector(".main-feed-scroll");
      if (newFeed) newFeed.scrollTop = scrollY;
    }
  }

  function bindMobileChrome() {
    const feed = document.querySelector(".main-feed-scroll");
    const header = document.querySelector(".header-bar");
    if (!feed || !header || !isMobileViewport()) {
      header?.classList.remove("header-hidden");
      document.body.classList.remove("mobile-chrome-hidden");
      return;
    }

    if (feed.dataset.mobileScrollBound) return;
    feed.dataset.mobileScrollBound = "1";
    let lastY = feed.scrollTop;
    feed.addEventListener(
      "scroll",
      () => {
        if (!isMobileViewport()) {
          header.classList.remove("header-hidden");
          return;
        }
        const y = feed.scrollTop;
        if (y > lastY + 8 && y > 48) {
          header.classList.add("header-hidden");
          document.body.classList.add("mobile-chrome-hidden");
        } else if (y < lastY - 8 || y <= 8) {
          header.classList.remove("header-hidden");
          document.body.classList.remove("mobile-chrome-hidden");
        }
        lastY = y;
      },
      { passive: true }
    );
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
