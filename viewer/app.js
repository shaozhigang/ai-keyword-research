const DIMENSIONS = [
  { key: "D1", label: "趋势热度" },
  { key: "D2", label: "竞争空间" },
  { key: "D3", label: "痛点明确度" },
  { key: "D4", label: "工具可行性" },
  { key: "D5", label: "变现潜力" },
  { key: "D6", label: "差异化空间" },
];

const SOURCE_LABELS = {
  huggingface: "HF",
  producthunt: "PH",
  arxiv: "arXiv",
};

let state = {
  terms: [],
  filter: "all",
  search: "",
  competition: "",
  selectedTerm: null,
};

async function loadData() {
  const files = [
    "daily_raw.json",
    "daily_scored.json",
    "daily_pain.json",
    "pool_validated.json",
    "pool_watch.json",
  ];

  const [raw, scored, pain, validated, watch] = await Promise.all(
    files.map((f) =>
      fetch(`../keywords/${f}`).then((r) => {
        if (!r.ok) throw new Error(`无法加载 keywords/${f}`);
        return r.json();
      })
    )
  );

  return buildIndex(raw, scored, pain, validated, watch);
}

function getSources(breakdown, term) {
  const sources = [];
  for (const [key, list] of Object.entries(breakdown || {})) {
    if (list.includes(term)) sources.push(SOURCE_LABELS[key] || key);
  }
  return sources;
}

function buildIndex(raw, scored, pain, validated, watch) {
  const map = new Map();

  for (const term of raw.new_terms || []) {
    map.set(term, {
      term,
      sources: getSources(raw.source_breakdown, term),
      pool: null,
      scored: null,
      pain: null,
      poolEntry: null,
    });
  }

  for (const t of scored.terms || []) {
    if (!map.has(t.term)) {
      map.set(t.term, { term: t.term, sources: [], pool: null, scored: null, pain: null, poolEntry: null });
    }
    map.get(t.term).scored = t;
  }

  for (const t of pain.terms || []) {
    if (!map.has(t.term)) {
      map.set(t.term, { term: t.term, sources: [], pool: null, scored: null, pain: null, poolEntry: null });
    }
    map.get(t.term).pain = t;
  }

  for (const e of validated.entries || []) {
    const item = map.get(e.term) || { term: e.term, sources: [], scored: null, pain: null };
    item.pool = "validated";
    item.poolEntry = e;
    map.set(e.term, item);
  }

  for (const e of watch.entries || []) {
    const item = map.get(e.term) || { term: e.term, sources: [], scored: null, pain: null };
    if (!item.pool) {
      item.pool = "watch";
      item.poolEntry = e;
    }
    map.set(e.term, item);
  }

  return {
    date: raw.date || scored.date,
    painSignals: raw.pain_signals || [],
    terms: [...map.values()].sort((a, b) => {
      const sa = a.poolEntry?.total_score ?? -1;
      const sb = b.poolEntry?.total_score ?? -1;
      if (sb !== sa) return sb - sa;
      return a.term.localeCompare(b.term);
    }),
    counts: {
      new: (raw.new_terms || []).length,
      validated: (validated.entries || []).length,
      watch: (watch.entries || []).length,
    },
  };
}

function isNoise(text) {
  if (!text || typeof text !== "string") return true;
  if (text.startsWith("!(data:image")) return true;
  if (text.length > 300 && text.includes("base64")) return true;
  return false;
}

function cleanPainItems(items) {
  return (items || []).filter((t) => !isNoise(t));
}

function trendClass(trend) {
  if (!trend) return "badge-trend-flat";
  if (trend.includes("上升")) return "badge-trend-up";
  if (trend.includes("下降")) return "badge-trend-down";
  return "badge-trend-flat";
}

function compClass(comp) {
  if (comp === "高") return "badge-comp-high";
  if (comp === "中") return "badge-comp-mid";
  if (comp === "低") return "badge-comp-low";
  return "";
}

function scoreBarClass(val) {
  if (val <= 1) return "low";
  if (val <= 3) return "mid";
  return "high";
}

function getFilteredTerms() {
  let list = state.terms;

  if (state.filter === "validated") list = list.filter((t) => t.pool === "validated");
  else if (state.filter === "watch") list = list.filter((t) => t.pool === "watch");
  else if (state.filter === "pipeline") list = list.filter((t) => t.scored && t.pain);

  if (state.competition) {
    list = list.filter((t) => (t.scored?.competition || t.poolEntry?.competition) === state.competition);
  }

  if (state.search) {
    const q = state.search.toLowerCase();
    list = list.filter((t) => t.term.toLowerCase().includes(q));
  }

  return list;
}

function renderKpis(data) {
  document.getElementById("kpi-date").textContent = data.date || "—";
  document.getElementById("kpi-new").textContent = data.counts.new;
  document.getElementById("kpi-validated").textContent = data.counts.validated;
  document.getElementById("kpi-watch").textContent = data.counts.watch;

  document.getElementById("count-all").textContent = data.terms.length;
  document.getElementById("count-validated").textContent = data.counts.validated;
  document.getElementById("count-watch").textContent = data.counts.watch;
  document.getElementById("count-pipeline").textContent = data.terms.filter((t) => t.scored && t.pain).length;
}

function renderTermCard(item) {
  const s = item.scored || item.poolEntry || {};
  const score = item.poolEntry?.total_score;
  const poolBadge =
    item.pool === "validated"
      ? '<span class="badge badge-pool-validated">验证池</span>'
      : item.pool === "watch"
        ? '<span class="badge badge-pool-watch">观察池</span>'
        : "";

  const sourceBadges = item.sources.map((s) => `<span class="badge badge-source">${s}</span>`).join("");

  return `
    <div class="term-card ${state.selectedTerm === item.term ? "selected" : ""}" data-term="${escapeAttr(item.term)}">
      <div class="term-card-header">
        <span class="term-name">${escapeHtml(item.term)}</span>
        ${score != null ? `<span class="score-pill">${score} 分</span>` : ""}
      </div>
      <div class="term-meta">
        ${s.trend ? `<span class="badge ${trendClass(s.trend)}">${escapeHtml(s.trend)}</span>` : ""}
        ${s.competition ? `<span class="badge ${compClass(s.competition)}">竞争${escapeHtml(s.competition)}</span>` : ""}
        ${poolBadge}
        ${sourceBadges}
      </div>
    </div>
  `;
}

function renderPainBlock(label, items) {
  const cleaned = cleanPainItems(items);
  if (!cleaned.length) return "";
  const lis = cleaned.map((text) => `<li>${escapeHtml(text)}</li>`).join("");
  return `
    <p class="pain-type">${escapeHtml(label)}</p>
    <ul class="pain-list">${lis}</ul>
  `;
}

function renderDetail(item) {
  if (!item) {
    return '<div class="detail-empty">点击左侧词条查看详情</div>';
  }

  const s = item.scored || {};
  const p = item.poolEntry || {};
  const pain = item.pain || {};
  const entry = item.poolEntry;

  const hasRaw = item.sources.length > 0;
  const hasScored = !!item.scored;
  const hasPain = !!item.pain;
  const hasPool = !!item.pool;

  let poolSection = "";
  if (entry) {
    const scores = entry.scores || {};
    const bars = DIMENSIONS.map((d) => {
      const val = scores[d.key] ?? 0;
      return `
        <div class="score-row">
          <label>${d.label}</label>
          <div class="bar-track"><div class="bar-fill ${scoreBarClass(val)}" style="width:${(val / 5) * 100}%"></div></div>
          <span class="score-val">${val}</span>
        </div>
      `;
    }).join("");

    poolSection = `
      <div class="section">
        <div class="section-title"><span class="step">4</span>最终打分</div>
        <div class="total-score">${entry.total_score} <small>/ 30</small></div>
        <div class="score-bars">${bars}</div>
        <p style="margin-top:10px;font-size:0.82rem;color:var(--text-muted)">状态：${escapeHtml(entry.status || "")}</p>
      </div>
    `;

    if (entry.product_direction) {
      poolSection += `
        <div class="highlight-box">
          <div class="headline">${escapeHtml(entry.suggested_headline || "")}</div>
          <p>${escapeHtml(entry.product_direction)}</p>
          ${
            entry.target_users?.length
              ? `<div class="tag-list" style="margin-top:10px">${entry.target_users.map((u) => `<span class="tag">${escapeHtml(u)}</span>`).join("")}</div>`
              : ""
          }
        </div>
      `;
    }
  }

  return `
    <h2>${escapeHtml(item.term)}</h2>

    <div class="pipeline-flow">
      <div class="pipeline-step ${hasRaw ? "done" : ""}">① 扫新词</div>
      <div class="pipeline-step ${hasScored ? "done" : ""}">② 趋势竞争</div>
      <div class="pipeline-step ${hasPain ? "done" : ""}">③ 找抱怨</div>
      <div class="pipeline-step ${hasPool ? "done" : ""}">④ 打分入池</div>
    </div>

    ${poolSection}

    ${
      hasScored
        ? `
      <div class="section">
        <div class="section-title"><span class="step">2</span>趋势 & 竞争</div>
        <div class="info-grid">
          <div class="info-item"><label>趋势</label>${escapeHtml(s.trend || "—")}</div>
          <div class="info-item"><label>竞争</label>${escapeHtml(s.competition || "—")}</div>
          <div class="info-item"><label>主要地区</label>${escapeHtml(s.main_geo || "—")}</div>
          <div class="info-item"><label>Top10 质量</label>${escapeHtml(s.top10_quality || "—")}</div>
        </div>
      </div>
    `
        : ""
    }

    ${
      hasRaw
        ? `
      <div class="section">
        <div class="section-title"><span class="step">1</span>来源</div>
        <div class="tag-list">${item.sources.map((src) => `<span class="tag">${escapeHtml(src)}</span>`).join("") || '<span class="tag">—</span>'}</div>
      </div>
    `
        : ""
    }

    ${
      hasPain
        ? `
      <div class="section">
        <div class="section-title"><span class="step">3</span>用户抱怨 & 痛点</div>
        ${renderPainBlock("抱怨", pain.top_complaints)}
        ${renderPainBlock("绕路方案", pain.workarounds)}
        ${renderPainBlock("期望功能", pain.desired_features)}
        ${
          !cleanPainItems(pain.top_complaints).length &&
          !cleanPainItems(pain.workarounds).length &&
          !cleanPainItems(pain.desired_features).length
            ? '<p style="color:var(--text-muted);font-size:0.85rem">暂无有效痛点数据</p>'
            : ""
        }
      </div>
    `
        : ""
    }
  `;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, "&#39;");
}

function render() {
  const list = getFilteredTerms();
  const listEl = document.getElementById("term-list");
  listEl.innerHTML = list.length
    ? list.map(renderTermCard).join("")
    : '<div class="detail-empty">没有匹配的词条</div>';

  const selected = state.terms.find((t) => t.term === state.selectedTerm);
  document.getElementById("detail-panel").innerHTML = renderDetail(selected);
}

function bindEvents() {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.filter = btn.dataset.filter;
      render();
    });
  });

  document.getElementById("search").addEventListener("input", (e) => {
    state.search = e.target.value.trim();
    render();
  });

  document.getElementById("competition-filter").addEventListener("change", (e) => {
    state.competition = e.target.value;
    render();
  });

  document.getElementById("term-list").addEventListener("click", (e) => {
    const card = e.target.closest(".term-card");
    if (!card) return;
    state.selectedTerm = card.dataset.term;
    document.getElementById("detail-panel").classList.add("open");
    document.getElementById("detail-backdrop").classList.add("open");
    render();
  });

  document.getElementById("detail-backdrop").addEventListener("click", () => {
    document.getElementById("detail-panel").classList.remove("open");
    document.getElementById("detail-backdrop").classList.remove("open");
  });
}

async function init() {
  try {
    const data = await loadData();
    state.terms = data.terms;
    state.selectedTerm = data.terms.find((t) => t.pool === "validated")?.term || null;

    document.getElementById("loading").style.display = "none";
    document.getElementById("app").style.display = "grid";

    renderKpis(data);
    bindEvents();
    render();
  } catch (err) {
    document.getElementById("loading").style.display = "none";
    const el = document.getElementById("error");
    el.style.display = "flex";
    el.innerHTML = `
      <p>${escapeHtml(err.message)}</p>
      <p>请在仓库根目录启动本地服务器：</p>
      <code>python -m http.server 8080</code>
      <p>然后访问 <code>http://localhost:8080/viewer/</code></p>
    `;
  }
}

init();
