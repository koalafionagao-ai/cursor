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
    if (unread === 0) return t(`已读 ${total}`, `read ${total}`);
    if (unread === total) return `${unread}`;
    return `${unread}/${total}`;
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
  return `<div class="dashboard-card">
      <div class="stat-hero">
        <div class="stat-primary">
          <span class="stat-number">${s.unread}</span>
          <span class="stat-unit">${t("条未读", "unread")}</span>
        </div>
        <p class="stat-equation">${t("本月", "This month")} <strong>${s.total}</strong> ${t("条", "items")}
          = <span class="stat-unread">${s.unread}</span> ${t("未读", "unread")}
          + <span class="stat-read">${s.read}</span> ${t("已读", "read")}</p>
      </div>
      <div class="stat-secondary">
        <span>${t("未读分布在", "Unread across")} <strong>${s.daysWithUnread}</strong> ${t("天", "days")}
          · <strong>${s.catsWithUnread}</strong> ${t("个分类", "categories")}
          · <strong>${s.tagsWithUnread}</strong> ${t("个标签", "tags")}</span>
      </div>
      <p class="stat-hint">${t("追平基准日", "Catch-up baseline")}: <strong>${lv || t("无（全部算未读）", "none — all unread")}</strong>
        · ${t("最新简报", "Latest")}: <strong>${manifest?.latest_date || "-"}</strong></p>
      <p class="stat-hint muted">${t("历史日期无红点 = 该日早于基准日或已标已读，不是自动全员已读。", "No dot on older dates = before baseline or marked read.")}</p>
    </div>`;
  }

  function renderMain() {
    const el = document.getElementById("main-panel");
    const items = getVisibleItems();
    const toolbar = `<div class="toolbar">
        <button type="button" class="chip${filterUnread ? " active" : ""}" id="btn-unread-filter">${filterUnread ? t("仅未读", "Unread only") : t("显示全部（含已读）", "Show all incl. read")}</button>
        <button type="button" class="chip" id="btn-mark-all">${t("本页标为已读", "Mark visible read")}</button>
        <button type="button" class="chip" id="btn-catch-up">${t("追平至最新日", "Catch up to latest")}</button>
        <button type="button" class="chip chip-ghost" id="btn-reset-read">${t("重置阅读记录", "Reset read state")}</button>
      </div>`;

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
            <h3>${cat.emoji} ${lang === "zh" ? cat.zh : cat.en}
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
      title = t(`日报 ${route.date}`, `Daily ${route.date}`) + ` · ${countLabel(st.unread, st.total)}`;
    } else if (route.view === "tag") {
      const st = monthStats.byTag[route.tag] || { total: 0, unread: 0 };
      title = t(`标签 ${route.tag}`, `Tag ${route.tag}`) + ` · ${countLabel(st.unread, st.total)}`;
    } else if (route.view === "cat") {
      const cat = manifest.categories.find((c) => c.id === route.cat);
      const st = monthStats.byCat[route.cat] || { total: 0, unread: 0 };
      title = (cat ? (lang === "zh" ? cat.zh : cat.en) : route.cat) + ` · ${countLabel(st.unread, st.total)}`;
    }

    const list = items.length
      ? items.map(renderCard).join("")
      : `<div class="empty">${filterUnread ? t("此处无未读", "No unread here") : t("无内容", "Empty")}</div>`;
    const extraDay =
      route.view === "day"
        ? `<button type="button" class="chip" id="btn-mark-day">${t("本日全部已读", "Mark day read")}</button>`
        : "";
    el.innerHTML = `<h2 class="view-title">${escapeHtml(title)}</h2>
      <div class="toolbar">
        <button type="button" class="chip chip-back" id="btn-back-hub">${t("← 本月面板", "← Month hub")}</button>
        <button type="button" class="chip${filterUnread ? " active" : ""}" id="btn-unread-filter">${filterUnread ? t("仅未读", "Unread only") : t("显示全部", "Show all")}</button>
        ${extraDay}
        <button type="button" class="chip" id="btn-mark-all">${t("本页标为已读", "Mark visible read")}</button>
      </div>
      <div class="blog-list">${list}</div>`;
  }

  function renderLeftNav() {
    const el = document.getElementById("left-nav");
    const s = monthStats;
    let html = `<p class="panel-title">${t("月份", "Months")}</p>`;

    for (const m of manifest.months || []) {
      const open = m.id === route.month;
      const isCurrent = m.id === route.month;
      const monthUnread = isCurrent ? s.unread : "—";
      html += `<div class="month-group"><div class="month-title${open ? " open" : ""}" data-month-toggle="${m.id}">
        <span>${lang === "zh" ? m.label_zh : m.label_en}</span>
        ${isCurrent ? `<span class="nav-count">${monthUnread} ${t("未读", "unread")}</span>` : ""}
        <span class="icon">▶</span></div><div class="month-days${open ? " open" : ""}">`;

      if (isCurrent) {
        const days = [...(monthData?.days || [])].sort((a, b) => b.date.localeCompare(a.date));
        for (const d of days) {
          const st = s.byDay[d.date] || { total: d.total, unread: 0 };
          const active = route.view === "day" && route.date === d.date ? " active" : "";
          html += `<button type="button" class="nav-item${active}" data-day="${d.date}">
            <span>${d.date.slice(5)}</span>
            <span class="nav-count ${st.unread ? "" : "muted"}">${countLabel(st.unread, st.total)}</span>
          </button>`;
        }
      }
      html += `</div></div>`;
    }

    html += `<p class="panel-title">${t("分类（本月）", "Categories")}</p><div class="nav-stack">`;
    for (const cat of manifest.categories || []) {
      const st = s.byCat[cat.id] || { total: 0, unread: 0 };
      if (st.total === 0) continue;
      const active = route.view === "cat" && route.cat === cat.id ? " active" : "";
      html += `<button type="button" class="nav-item${active}" data-cat="${cat.id}">
        <span>${cat.emoji} ${lang === "zh" ? cat.zh : cat.en}</span>
        <span class="nav-count ${st.unread ? "" : "muted"}">${countLabel(st.unread, st.total)}</span>
      </button>`;
    }
    html += `</div>`;
    el.innerHTML = html;
  }

  function renderTagPanel() {
    const el = document.getElementById("tag-panel");
    const s = monthStats;
    const groups = window.AI_DAILY_TAG_GROUPS || [];
    const used = new Set(Object.keys(s.byTag));
    let html = `<p class="panel-title">${t("标签（本月）", "Tags this month")}</p>
      <p class="panel-hint">${t("数字 = 未读/本月共出现", "Numbers = unread / total in month")}</p>`;

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
        html += `<button type="button" class="chip chip-tag${active}" data-tag-nav="${escapeHtml(tag)}">
          <span class="tag-name">${escapeHtml(tag)}</span>
          <span class="nav-count ${unread ? "" : "muted"}">${unread}/${total}</span>
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
        html += `<button type="button" class="chip chip-tag${active}" data-tag-nav="${escapeHtml(tag)}">
          <span class="tag-name">${escapeHtml(tag)}</span>
          <span class="nav-count ${st.unread ? "" : "muted"}">${st.unread}/${st.total}</span>
        </button>`;
      }
      html += `</div></div>`;
    }

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
      if (cat) navigate(`#/${route.month}/cat/${encodeURIComponent(cat.dataset.cat)}`);
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
      if (e.target.id === "btn-reset-read") {
        resetReadState();
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
    document.getElementById("page-desc").textContent =
      lang === "zh"
        ? "本月未读优先；数字均为未读/总数，可直接相加理解。"
        : "Unread-first this month; counts are unread/total.";
    render();
  }

  async function loadMonth(month) {
    monthData = await fetchJSON("data/monthly/" + month + ".json");
    monthStats = computeMonthStats();
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
