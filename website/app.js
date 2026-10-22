(function () {
  "use strict";

  var PARTS = [
    ["01", "ファントムブラッド", "PHANTOM BLOOD"],
    ["02", "戦闘潮流", "BATTLE TENDENCY"],
    ["03", "スターダストクルセイダース", "STARDUST"],
    ["04", "ダイヤモンドは砕けない", "DIAMOND"],
    ["05", "黄金の風", "GOLDEN WIND"],
    ["06", "ストーンオーシャン", "STONE OCEAN"],
    ["07", "スティール・ボール・ラン", "STEEL BALL RUN"],
    ["08", "ジョジョリオン", "JOJOLION"],
    ["09", "The JOJOLands", "THE JOJOLANDS"]
  ];
  var LANGUAGES = { ja: "日本語", en: "英語", fr: "フランス語", pt: "ポルトガル語", es: "スペイン語" };

  function split(value) { return String(value || "").split(";").map(function (v) { return v.trim(); }).filter(Boolean); }
  function normalize(value) { return String(value || "").normalize("NFKC").toLocaleLowerCase("ja").replace(/\s+/g, " ").trim(); }
  function safeUrl(value) {
    try { var u = new URL(String(value)); return /^(https?:)$/.test(u.protocol) ? u.href : null; } catch (_) { return null; }
  }
  function parseState(search, themes) {
    var params = new URLSearchParams(search || "");
    var state = { q: (params.get("q") || "").slice(0, 300), part: params.get("part") || "", theme: params.get("theme") || "", relation: params.get("relation") || "", lang: params.get("lang") || "" };
    if (!PARTS.some(function (p) { return p[0] === state.part; })) state.part = "";
    if (themes && !themes.includes(state.theme)) state.theme = "";
    if (!["direct", "context"].includes(state.relation)) state.relation = "";
    if (!["ja", "other"].includes(state.lang)) state.lang = "";
    return state;
  }
  function selectRecords(records, state) {
    var words = normalize(state.q).split(" ").filter(Boolean);
    return records.filter(function (r) {
      if (state.part && !split(r.parts).includes(state.part)) return false;
      if (state.theme && !split(r.fields).includes(state.theme)) return false;
      if (state.relation && r.relation !== state.relation) return false;
      if (state.lang === "ja" && r.language !== "ja") return false;
      if (state.lang === "other" && r.language === "ja") return false;
      if (words.length) {
        var haystack = normalize([r.title, r.authors, r.fields, r.connection, r.source, r.source_type].join(" "));
        if (!words.every(function (word) { return haystack.includes(word); })) return false;
      }
      return true;
    }).slice().sort(function (a, b) {
      var relationOrder = (a.relation === "direct" ? 0 : 1) - (b.relation === "direct" ? 0 : 1);
      return relationOrder || String(a.id).localeCompare(String(b.id), "ja", { numeric: true });
    });
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { selectRecords: selectRecords, parseState: parseState, safeUrl: safeUrl, normalize: normalize };
  if (typeof document === "undefined") return;

  var records = Array.isArray(window.JOJO_CATALOG) ? window.JOJO_CATALOG : [];
  var results = document.getElementById("results");
  if (!results) return;
  var form = document.getElementById("filter-form");
  var search = document.getElementById("search");
  var theme = document.getElementById("theme-filter");
  var relation = document.getElementById("relation-filter");
  var language = document.getElementById("language-filter");
  var partFilters = document.getElementById("part-filters");
  var resultCount = document.getElementById("result-count");
  var resetButton = document.getElementById("reset-filters");
  var emptyState = document.getElementById("empty-state");
  var themeCounts = {};
  records.forEach(function (r) { split(r.fields).forEach(function (t) { themeCounts[t] = (themeCounts[t] || 0) + 1; }); });
  var themes = Object.keys(themeCounts).sort(function (a, b) { return themeCounts[b] - themeCounts[a] || a.localeCompare(b, "ja"); });
  var state = parseState(window.location.search, themes);

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function externalLink(label, url, className) {
    var safe = safeUrl(url);
    if (!safe) return null;
    var a = el("a", className, label);
    a.href = safe;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  }
  function appendDetail(dl, name, value) {
    if (!value) return;
    dl.appendChild(el("dt", "", name));
    dl.appendChild(el("dd", "", value));
  }
  function authorLabel(r) {
    var authors = split(r.authors);
    return authors.length > 3 ? authors.slice(0, 3).join("・") + " ほか（" + authors.length + "名）" : authors.join("・");
  }
  function createCard(r) {
    var article = el("article", "record-card" + (r.relation === "direct" ? " direct" : ""));
    article.setAttribute("aria-labelledby", "title-" + r.id);
    var meta = el("div", "card-meta");
    meta.appendChild(el("span", "relation-tag", r.relation === "direct" ? "ジョジョ自体を扱う研究" : "背景を知るための資料"));
    meta.appendChild(el("span", "language-label", LANGUAGES[r.language] || r.language));
    article.appendChild(meta);
    var title = el("h3", "card-title", r.title);
    title.id = "title-" + r.id;
    article.appendChild(title);
    article.appendChild(el("p", "card-authors", authorLabel(r) + " · " + r.year));
    article.appendChild(el("p", "connection", r.connection));
    var tags = el("div", "card-tags");
    split(r.parts).forEach(function (p) { tags.appendChild(el("span", "part-tag", /^0[1-9]$/.test(p) ? "第" + Number(p) + "部" : p)); });
    split(r.fields).slice(0, 4).forEach(function (t) { tags.appendChild(el("span", "theme-tag", t)); });
    article.appendChild(tags);
    if (/503/.test(r.access_status || "")) article.appendChild(el("p", "access-warning", "公開全文を確認済みですが、その後の再取得時に接続エラーが出ています。つながらない場合は時間をおいて開いてください。"));
    var actions = el("div", "card-actions");
    var fulltext = externalLink("無料の全文を読む", r.fulltext_url, "fulltext-link");
    if (fulltext) {
      var arrow = el("span", "", "↗"); arrow.setAttribute("aria-hidden", "true"); fulltext.appendChild(arrow);
      fulltext.setAttribute("aria-label", r.title + " — 無料の全文を外部サイトで読む");
      actions.appendChild(fulltext);
    }
    if (r.id === "jojo-001") {
      var note = el("a", "note-link", "読書メモを読む →");
      note.href = "./notes/jojo-001.html";
      actions.appendChild(note);
    }
    article.appendChild(actions);
    if (safeUrl(r.fulltext_url)) article.appendChild(el("p", "source-host", new URL(r.fulltext_url).hostname.replace(/^www\./, "")));
    var details = el("details", "card-details");
    details.appendChild(el("summary", "", "資料の詳細・確認記録"));
    var dl = el("dl", "detail-list");
    appendDetail(dl, "著者", split(r.authors).join("・"));
    appendDetail(dl, "発行年", r.year);
    appendDetail(dl, "掲載先", r.source);
    appendDetail(dl, "資料の種類", r.source_type);
    appendDetail(dl, "テーマ", split(r.fields).join("・"));
    appendDetail(dl, "査読", r.peer_review);
    appendDetail(dl, "公開状況", r.access_status);
    appendDetail(dl, "確認日", r.checked_on);
    appendDetail(dl, "確認範囲", r.verification_scope);
    appendDetail(dl, "利用条件", r.license || "未確認");
    appendDetail(dl, "補足", r.notes);
    details.appendChild(dl);
    var links = el("div", "detail-links");
    var landing = externalLink("書誌ページ ↗", r.landing_url);
    if (landing) links.appendChild(landing);
    if (r.doi && /^10\.\d{4,9}\/\S+$/.test(r.doi)) {
      var doi = externalLink("DOI ↗", "https://doi.org/" + r.doi);
      if (doi) links.appendChild(doi);
    }
    details.appendChild(links);
    article.appendChild(details);
    return article;
  }
  function setUrl() {
    var url = new URL(window.location.href);
    ["q", "part", "theme", "relation", "lang"].forEach(function (key) { if (state[key]) url.searchParams.set(key, state[key]); else url.searchParams.delete(key); });
    try { window.history.replaceState(null, "", url.pathname + url.search + url.hash); } catch (_) { /* Filtering still works if history is unavailable. */ }
  }
  function syncControls() {
    if (search.value !== state.q) search.value = state.q;
    theme.value = state.theme;
    relation.value = state.relation;
    language.value = state.lang;
    partFilters.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.part === state.part)); });
  }
  function render(updateUrl) {
    var filtered = selectRecords(records, state);
    var fragment = document.createDocumentFragment();
    filtered.forEach(function (r) { fragment.appendChild(createCard(r)); });
    results.replaceChildren(fragment);
    var count = el("strong", "", String(filtered.length));
    resultCount.replaceChildren(count, document.createTextNode("件の資料 / 全" + records.length + "件"));
    var labels = [];
    if (state.part) labels.push("第" + Number(state.part) + "部");
    if (state.theme) labels.push(state.theme);
    if (state.relation) labels.push(state.relation === "direct" ? "直接研究" : "背景資料");
    if (state.lang) labels.push(state.lang === "ja" ? "日本語" : "日本語以外");
    if (state.q) labels.push("「" + state.q + "」");
    if (labels.length) resultCount.appendChild(el("span", "result-context", labels.join(" / ")));
    resetButton.disabled = !Object.keys(state).some(function (key) { return Boolean(state[key]); });
    emptyState.hidden = filtered.length > 0;
    results.hidden = filtered.length === 0;
    syncControls();
    if (updateUrl) setUrl();
  }
  function reset() {
    state = { q: "", part: "", theme: "", relation: "", lang: "" };
    render(true);
  }

  themes.forEach(function (t) {
    var option = el("option", "", t + "（" + themeCounts[t] + "）"); option.value = t; theme.appendChild(option);
  });
  [["", "すべての部", "ALL PARTS"]].concat(PARTS).forEach(function (p) {
    var count = p[0] ? records.filter(function (r) { return split(r.parts).includes(p[0]); }).length : records.length;
    var button = el("button", "part-button");
    button.type = "button";
    button.dataset.part = p[0];
    button.dataset.short = p[2];
    button.setAttribute("aria-label", (p[0] ? "第" + Number(p[0]) + "部 " : "") + p[1] + "、" + count + "件");
    var top = el("span", "part-button-top");
    top.appendChild(el("span", "", p[0] ? "第" + Number(p[0]) + "部" : "すべて"));
    top.appendChild(el("span", "part-count", String(count)));
    button.appendChild(top);
    button.appendChild(el("span", "part-name", p[0] ? p[1] : "ALL PARTS"));
    button.addEventListener("click", function () { state.part = p[0]; render(true); });
    partFilters.appendChild(button);
  });
  var composing = false;
  function updateSearch() { state.q = search.value.slice(0, 300); render(true); }
  search.addEventListener("compositionstart", function () { composing = true; });
  search.addEventListener("compositionend", function () { composing = false; updateSearch(); });
  search.addEventListener("input", function (event) { if (!composing && !event.isComposing) updateSearch(); });
  theme.addEventListener("change", function () { state.theme = theme.value; render(true); });
  relation.addEventListener("change", function () { state.relation = relation.value; render(true); });
  language.addEventListener("change", function () { state.lang = language.value; render(true); });
  form.addEventListener("submit", function (event) { event.preventDefault(); state.q = search.value.slice(0, 300); render(true); search.blur(); });
  resetButton.addEventListener("click", reset);
  document.getElementById("empty-reset").addEventListener("click", reset);
  window.addEventListener("popstate", function () { state = parseState(window.location.search, themes); render(false); });
  document.getElementById("back-to-top").addEventListener("click", function (event) { event.preventDefault(); window.scrollTo({ top: 0, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); });
  var dates = records.map(function (r) { return r.checked_on; }).filter(Boolean).sort();
  if (dates.length) {
    var date = dates[dates.length - 1];
    document.getElementById("checked-date").dateTime = date;
    document.getElementById("checked-date").textContent = date.replace(/-/g, ".");
  }
  if (!records.length) {
    resultCount.textContent = "資料データを読み込めませんでした。ページを再読み込みしてください。";
    emptyState.hidden = false;
    emptyState.querySelector("h3").textContent = "資料データを読み込めませんでした。";
    emptyState.querySelector("p").textContent = "再読み込みしても開けない場合は、下の「文献目録・出典」から資料を読めます。";
    document.getElementById("empty-reset").hidden = true;
  } else render(false);
})();
