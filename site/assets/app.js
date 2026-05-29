/**
 * AI Daily 聚合页 v2：统计口径统一、标签分组、已读状态可见
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

  function markDayRead(date) {
    monthData?.items?.filter((it) => it.date === date).forEach((it) => markRead(it.date, it.id));
    render();
  }

  function markAllVisibleRead() {
    getVisibleItems(false).forEach((it) => markRead(it.date, it.id));
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

  function resetReadState() {
    if (confirm(t("确定清空本机阅读记录？", "Clear all read state on this device?"))) {
      localStorage.removeItem(STORAGE_KEY);
      render();
    }
  }

  /**
   * 未读 = 未单独标已读，且简报日期晚于「追平基准日」。
   * 历史无红点：通常因已「追平至最新日」或曾标已读，不等于服务器侧已读。
   */
  function isUnreadItem(it) {
    if (isExplicitlyRead(it.date, it.id)) return false;
    const lv = getLastVisit();
    if (!lv) return true;
    return it.date > lv;
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

  function renderFilterChips() {
    return `<div class="toolbar-filters">
      <button type="button" class="chip chip-filter${filterUnread ? " active" : ""}" id="btn-filter-unread">${t("未读", "Unread")}</button>
      <button type="button" class="chip chip-filter${!filterUnread ? " active" : ""}" id="btn-filter-all">${t("全部", "All")}</button>
    </div>`;
  }

  function renderActionChips(opts = {}) {
    const { catchUp = false, markDay = false } = opts;
    let html = `<div class="toolbar-actions">`;
    if (markDay) {
      html += `<button type="button" class="chip chip-act" id="btn-mark-day">${t("全部已读", "Mark all read")}</button>`;
    } else {
      html += `<button type="button" class="chip chip-act" id="btn-mark-all">${t("全部已读", "Mark all read")}</button>`;
    }
    if (catchUp) {
      html += `<button type="button" class="chip chip-act" id="btn-catch-up">${t("追平到最新", "Catch up to latest")}</button>`;
    }
    html += `</div>`;
    return html;
  }

  function renderToolbar(opts = {}) {
    const { catchUp = false, markDay = false } = opts;
    return `<div class="toolbar">${renderFilterChips()}${renderActionChips({ catchUp, markDay })}</div>`;
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
        <span class="meta-line">${escapeHtml(it.source)} · ${it.date}</span>
        <span class="tag-row">${tags}</span>
        <button type="button" class="mark-read-btn" data-mark="${it.date}:${it.id}">${read ? t("标为未读", "Mark unread") : t("标为已读", "Mark read")}</button>
      </div>
    </a>`;
  }

  function renderDashboard() {
    const s = monthStats;
    const lv = getLastVisit();
  const ml = monthLabelFor(route.month);
  return `<div class="dashboard-card dashboard-compact">
      <p class="stat-latest">${t("最新简报", "Latest brief")}: <strong class="stat-latest-date">${manifest?.latest_date || "-"}</strong></p>
      <div class="stat-headline">
        <span class="stat-month-big">${escapeHtml(ml)}</span>
        <span class="stat-primary">
          <span class="stat-number">${s.unread}</span>
          <span class="stat-unit">${t("条未读", "unread")}</span>
        </span>
      </div>
      <p class="stat-equation">${t("本月", "This month")} <strong>${s.total}</strong> ${t("条", "items")}
        = <span class="stat-unread">${s.unread}</span> ${t("未读", "unread")}
        + <span class="stat-read">${s.read}</span> ${t("已读", "read")}
        · ${t("未读分布在", "Unread across")} <strong>${s.daysWithUnread}</strong> ${t("天", "days")}
        · <strong>${s.catsWithUnread}</strong> ${t("分类", "cat")}
        · <strong>${s.tagsWithUnread}</strong> ${t("标签", "tags")}</p>
      <p class="stat-meta">${t("追平基准日", "Baseline")}: <strong>${lv || t("无", "none")}</strong></p>
    </div>`;
  }

  function renderMain() {
    const el = document.getElementById("main-panel");
    const items = getVisibleItems();
    const toolbar = renderToolbar({ catchUp: true });

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
      el.innerHTML = renderDashboard() + toolbar + body;
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
    const subToolbar = renderToolbar({ markDay: route.view === "day", catchUp: false });
    el.innerHTML = `${backLink}<h2 class="view-title">${escapeHtml(title)}</h2>${subToolbar}<div class="blog-list">${list}</div>`;
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

  function renderLeftNav() {
    const el = document.getElementById("left-nav");
    let html = `<p class="panel-title">${t("时间", "Timeline")}</p><div class="nav-scroll">`;

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
            <button type="button" class="month-label" data-month-nav="${m.id}">${escapeHtml(m.id)}</button>
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
            html += `<button type="button" class="nav-item${active}" data-day="${d.date}">
              <span>${d.date.slice(8, 10) || d.date.slice(5)}</span>
              <span class="nav-count ${st.unread ? "" : "muted"}">${countLabel(st.unread, st.total)}</span>
            </button>`;
          }
        }
        html += `</div></div>`;
      }
      html += `</div></div>`;
    }

    html += `</div>`;
    el.innerHTML = html;
  }

  function renderTagPanel() {
    const el = document.getElementById("tag-panel");
    const s = monthStats;
    const groups = window.AI_DAILY_TAG_GROUPS || [];
    const used = new Set(Object.keys(s.byTag));
    let html = `<p class="panel-title">${t("分类（本月）", "Categories")}</p><div class="nav-stack compact-nav">`;
    for (const cat of manifest.categories || []) {
      const st = s.byCat[cat.id] || { total: 0, unread: 0 };
      if (st.total === 0) continue;
      const active = route.view === "cat" && route.cat === cat.id ? " active" : "";
      html += `<button type="button" class="nav-item${active}" data-cat="${cat.id}">
        <span>${lang === "zh" ? cat.zh : cat.en}</span>
        <span class="nav-count ${st.unread ? "" : "muted"}">${countLabel(st.unread, st.total)}</span>
      </button>`;
    }
    html += `</div><p class="panel-title">${t("标签（本月）", "Tags")}</p>
      <p class="panel-hint">${t("未读/本月出现；全读显示置灰", "Unread/total; all-read grayed")}</p>
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

    html += `</div>`;
    el.innerHTML = html;
  }

  function bindEvents() {
    document.getElementById("btn-en")?.addEventListener("click", () => switchLang("en"));
    document.getElementById("btn-zh")?.addEventListener("click", () => switchLang("zh"));

    document.getElementById("left-nav")?.addEventListener("click", async (e) => {
      const yt = e.target.closest("[data-year-toggle]");
      if (yt) {
        e.preventDefault();
        toggleYear(yt.dataset.yearToggle);
        renderLeftNav();
        return;
      }
      const mt = e.target.closest("[data-month-toggle]");
      if (mt) {
        e.preventDefault();
        const monthId = mt.dataset.monthToggle;
        toggleMonth(monthId);
        if (expandedMonths.has(monthId) && monthId !== route.month) await prefetchMonth(monthId);
        renderLeftNav();
        return;
      }
      const mn = e.target.closest("[data-month-nav]");
      if (mn) {
        navigate("#/" + mn.dataset.monthNav);
        return;
      }
      const day = e.target.closest("[data-day]");
      if (day) {
        const monthId = day.dataset.day.slice(0, 7);
        navigate(`#/${monthId}/day/${day.dataset.day}`);
        return;
      }
    });

    document.getElementById("tag-panel")?.addEventListener("click", (e) => {
      const tag = e.target.closest("[data-tag-nav]");
      if (tag) {
        navigate(`#/${route.month}/tag/${encodeURIComponent(tag.dataset.tagNav)}`);
        return;
      }
      const cat = e.target.closest("[data-cat]");
      if (cat) navigate(`#/${route.month}/cat/${encodeURIComponent(cat.dataset.cat)}`);
    });

    document.getElementById("main-panel")?.addEventListener("click", (e) => {
      if (e.target.id === "btn-filter-unread") {
        filterUnread = true;
        render();
        return;
      }
      if (e.target.id === "btn-filter-all") {
        filterUnread = false;
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
        if (isExplicitlyRead(d, id)) {
          const s = loadState();
          delete s.read?.[itemKey(d, id)];
          saveState(s);
        } else {
          markRead(d, id);
        }
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

  async function render() {
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
