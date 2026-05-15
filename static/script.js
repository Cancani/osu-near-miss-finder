// osu! Near-Miss Finder. Frontend logic.

const form = document.getElementById("search-form");
const statusEl = document.getElementById("status");
const userCard = document.getElementById("user-card");
const userAvatar = document.getElementById("user-avatar");
const userName = document.getElementById("user-name");
const userStats = document.getElementById("user-stats");
const resultCount = document.getElementById("result-count");
const resultsEl = document.getElementById("results");
const tpl = document.getElementById("score-template");

const MODE_LABELS = {
  osu: "osu!standard",
  taiko: "osu!taiko",
  fruits: "osu!catch",
  mania: "osu!mania",
};

const RANK_COLORS = {
  XH: "#e5e7eb",
  X: "#fbbf24",
  SH: "#e5e7eb",
  S: "#fbbf24",
  A: "#6ee7b7",
  B: "#60a5fa",
  C: "#c084fc",
  D: "#f87171",
  F: "#9ca3af",
};

function showStatus(msg, kind = "loading") {
  statusEl.className = `status ${kind}`;
  statusEl.classList.remove("hidden");
  if (kind === "loading") {
    statusEl.innerHTML = `<span class="spinner"></span><span>${msg}</span>`;
  } else {
    statusEl.textContent = msg;
  }
}

function hideStatus() { statusEl.classList.add("hidden"); }

function formatNum(n) {
  if (n == null) return "-";
  return new Intl.NumberFormat("en-US").format(n);
}

function formatPP(pp) {
  if (pp == null) return "-";
  return `${Math.round(pp)}pp`;
}

function renderUser(user, count, mode) {
  userAvatar.src = user.avatar_url || "";
  userName.textContent = user.username;

  const parts = [MODE_LABELS[mode] || mode];
  if (user.global_rank) parts.push(`#${formatNum(user.global_rank)} global`);
  if (user.pp) parts.push(`${formatNum(Math.round(user.pp))}pp`);
  if (user.country_code) parts.push(user.country_code);
  userStats.textContent = parts.join("  ·  ");

  resultCount.innerHTML = `<strong>${count}</strong> near-misses`;
  userCard.classList.remove("hidden");
}

function renderScore(score) {
  const node = tpl.content.cloneNode(true);
  const card = node.querySelector(".score-card");
  const cover = node.querySelector(".score-cover");
  const img = node.querySelector(".score-cover img");
  const badge = node.querySelector(".miss-badge");
  const title = node.querySelector(".score-title");
  const artist = node.querySelector(".score-artist");
  const version = node.querySelector(".score-version");
  const mods = node.querySelector(".score-mods");

  const bset = score.beatmapset || {};
  const bmap = score.beatmap || {};

  cover.href = bmap.url || `https://osu.ppy.sh/beatmapsets/${bset.id}`;
  img.src = bset.cover || "";
  img.alt = `${bset.title} cover`;

  const misses = score.miss_count ?? 0;
  badge.textContent = `${misses}× miss`;
  badge.dataset.misses = String(misses);

  title.textContent = bset.title || "(unknown)";
  artist.textContent = bset.artist ? `by ${bset.artist}` : "";
  version.textContent = bmap.version || "";

  const setStat = (selector, value) => {
    const el = node.querySelector(`${selector} .stat-value`);
    if (el) el.textContent = value;
  };

  setStat(".stat-stars", bmap.difficulty_rating ? bmap.difficulty_rating.toFixed(2) : "-");
  setStat(".stat-acc", `${score.accuracy.toFixed(2)}%`);

  const comboStr = bmap.max_combo
    ? `${formatNum(score.max_combo)}/${formatNum(bmap.max_combo)}`
    : formatNum(score.max_combo);
  setStat(".stat-combo", comboStr);

  setStat(".stat-pp", formatPP(score.pp));

  const rankEl = node.querySelector(".stat-rank .stat-value");
  if (rankEl) {
    rankEl.textContent = score.rank || "-";
    rankEl.style.color = RANK_COLORS[score.rank] || "var(--text)";
    rankEl.style.fontWeight = "700";
  }

  for (const mod of score.mods || []) {
    const m = document.createElement("span");
    m.className = "mod";
    m.textContent = mod;
    mods.appendChild(m);
  }

  // Stagger reveal
  card.style.animationDelay = `${Math.min(score._idx * 30, 600)}ms`;

  return node;
}

async function search(e) {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  if (!username) return;

  const params = new URLSearchParams({
    mode: document.getElementById("mode").value,
    score_type: document.getElementById("score_type").value,
    min_misses: document.getElementById("min_misses").value,
    max_misses: document.getElementById("max_misses").value,
    limit: document.getElementById("limit").value,
  });

  resultsEl.innerHTML = "";
  userCard.classList.add("hidden");
  showStatus(`Scanning ${username}…`);

  try {
    const resp = await fetch(
      `/api/near-misses/${encodeURIComponent(username)}?${params}`
    );
    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.detail || `HTTP ${resp.status}`);
    }

    hideStatus();
    renderUser(data.user, data.count, data.query.mode);

    if (data.scores.length === 0) {
      showStatus(
        `Scanned ${data.query.scanned} ${data.query.score_type} plays, none in range ${data.query.min_misses}-${data.query.max_misses} misses. Try widening the range.`,
        "info"
      );
      return;
    }

    const frag = document.createDocumentFragment();
    data.scores.forEach((s, i) => {
      s._idx = i;
      frag.appendChild(renderScore(s));
    });
    resultsEl.appendChild(frag);
  } catch (err) {
    console.error(err);
    showStatus(`Error: ${err.message}`, "error");
  }
}

form.addEventListener("submit", search);