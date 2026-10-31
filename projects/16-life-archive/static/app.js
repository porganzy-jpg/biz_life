// 나의 아카이브 — 화면 하나짜리 바닐라 JS

const KINDS = {
  movie: "영화", tv: "드라마·TV", anime: "애니", manga: "만화·웹툰", book: "책",
  game: "게임", music: "음악", place: "장소", event: "사건", person: "사람", thing: "기타",
  memo: "메모",
};

const state = { cards: [], settings: {}, results: [], kindFilter: "all", view: "timeline", allKind: "all" };
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: opts.body && !(opts.body instanceof FormData) ? { "Content-Type": "application/json" } : {},
    ...opts,
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

const birthYear = () => Number(state.settings.birth_year) || null;
const ageOf = (metYear) => (metYear && birthYear() ? metYear - birthYear() : null);

// ── 표지 ─────────────────────────────────────────────────
function cover(item, { photoFirst = false } = {}) {
  const img = photoFirst && item.photo ? `/photos/${item.photo}` : item.image || (item.photo ? `/photos/${item.photo}` : null);
  return `<div class="cover" style="--kc: var(--k-${esc(item.kind)})">
    <span class="kindtag">${esc(KINDS[item.kind] || "기타")}</span>
    ${img ? `<img src="${esc(img)}" alt="" loading="lazy" onerror="this.remove()">` : ""}
    <span>${esc(item.title)}</span>
  </div>`;
}

// ── 찾기 ─────────────────────────────────────────────────
const SOURCE_NAME = {
  wikidata: "Wikidata", kakao_book: "카카오 책", kakao_place: "카카오 장소",
  anilist: "AniList", musicbrainz: "MusicBrainz", tmdb: "TMDB", rawg: "RAWG",
};

async function runSearch(q) {
  $("#results").hidden = false;
  $("#result-grid").innerHTML = `<p class="sub">찾는 중…</p>`;
  $("#kind-chips").innerHTML = "";
  const { results, errors } = await api(`/api/search?q=${encodeURIComponent(q)}`);
  state.results = results;
  state.kindFilter = "all";
  const errs = Object.keys(errors);
  $("#search-errors").hidden = !errs.length;
  $("#search-errors").textContent = errs.length ? `응답 없음: ${errs.map((e) => SOURCE_NAME[e] || e).join(", ")}` : "";
  renderResults();
}

function renderResults() {
  const counts = {};
  state.results.forEach((r) => (counts[r.kind] = (counts[r.kind] || 0) + 1));
  const kinds = Object.keys(KINDS).filter((k) => counts[k]);
  $("#kind-chips").innerHTML = [`<button class="chip ${state.kindFilter === "all" ? "on" : ""}" data-k="all">전체 ${state.results.length}</button>`,
    ...kinds.map((k) => `<button class="chip ${state.kindFilter === k ? "on" : ""}" data-k="${k}">${KINDS[k]} ${counts[k]}</button>`)].join("");
  const shown = state.results
    .map((r, i) => ({ ...r, _i: i }))
    .filter((r) => state.kindFilter === "all" || r.kind === state.kindFilter);
  $("#result-grid").innerHTML = shown.length ? shown.map((r) => {
    const have = findExisting(r);
    return `<div class="hit" data-i="${r._i}">
      ${cover(r)}
      <div class="t">${esc(r.title)}${have ? " ✓" : ""}</div>
      <div class="s">${esc([r.year, r.subtitle].filter(Boolean).join(" · "))}</div>
      <div class="badge"><b>${esc(SOURCE_NAME[r.source] || r.source)}</b>${have ? " · 이미 담음" : ""}</div>
    </div>`;
  }).join("") : `<p class="sub">찾은 게 없어요. ‘직접 만들기’로 담을 수 있어요.</p>`;
}

const findExisting = (r) => r.source_id
  ? state.cards.find((c) => c.source === r.source && c.source_id === r.source_id)
  : null; // ISBN 없는 책처럼 ID가 비면 같은 작품이라고 단정하지 않는다

// ── 카드 편집 ─────────────────────────────────────────────
let editing = null; // {id?} + 필드

function openEditor(card) {
  editing = { ...card }; // 복사본을 고친다 — 취소하면 원본 카드는 그대로
  const f = $("#card-form");
  f.reset();
  $("#ed-kind").innerHTML = Object.entries(KINDS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  for (const el of f.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") el.checked = !!card[el.name];
    else el.value = card[el.name] ?? "";
  }
  $("#ed-age").value = ageOf(card.met_year) ?? "";
  $("#ed-photo").value = "";
  $("#ed-cover").innerHTML = cover(card, { photoFirst: true });
  $("#ed-delete").hidden = !card.id;
  $("#ed-save").textContent = card.id ? "저장" : "담기";
  $("#editor").showModal();
}

function fromHit(r) {
  return { kind: r.kind, title: r.title, subtitle: r.subtitle, year: r.year, image: r.image,
    source: r.source, source_id: r.source_id, url: r.url, links: r.links };
}

async function saveEditor() {
  const f = $("#card-form");
  const data = { ...editing };
  for (const el of f.elements) {
    if (!el.name) continue;
    data[el.name] = el.type === "checkbox" ? el.checked : el.type === "number" ? (el.value ? Number(el.value) : null) : el.value;
  }
  let saved = data.id
    ? await api(`/api/cards/${data.id}`, { method: "PUT", body: JSON.stringify(data) })
    : await api("/api/cards", { method: "POST", body: JSON.stringify(data) });
  const file = $("#ed-photo").files[0];
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    saved = await api(`/api/cards/${saved.id}/photo`, { method: "POST", body: fd });
  }
  await loadCards();
  if (!$("#results").hidden) renderResults();
}

// ── 본문 화면 ─────────────────────────────────────────────
function cardHTML(c) {
  const age = ageOf(c.met_year);
  const when = c.met_year ? `${age != null ? `${age}살 · ` : ""}${c.met_year}` : "";
  if (c.kind === "memo") {
    return `<article class="card note" data-id="${c.id}">
      ${c.pinned ? `<span class="pin">★</span>` : ""}
      <div class="note-text">${esc(c.memory || c.title)}</div>
      ${when ? `<div class="when">${esc(when)}</div>` : ""}
    </article>`;
  }
  return `<article class="card" data-id="${c.id}">
    <div style="position:relative">${c.pinned ? `<span class="pin">★</span>` : ""}${cover(c, { photoFirst: true })}</div>
    <div class="t">${esc(c.title)}</div>
    ${when ? `<div class="when">${esc(when)}</div>` : ""}
    ${c.memory ? `<div class="mem">${esc(c.memory)}</div>` : ""}
  </article>`;
}

// 연대기의 한 장 = 한 해. 그해 나이를 부제로 단다.
function chapters(cards) {
  const years = new Map();
  const unknown = [];
  for (const c of cards) {
    if (!c.met_year) { unknown.push(c); continue; }
    if (!years.has(c.met_year)) years.set(c.met_year, []);
    years.get(c.met_year).push(c);
  }
  const list = [...years.entries()].sort((a, b) => a[0] - b[0]).map(([year, cs]) => {
    const age = ageOf(year);
    return { name: `${year}`, cards: cs, range: age != null ? `${age}살` : "" };
  });
  if (unknown.length) list.push({ name: "언제였더라", cards: unknown, range: "해를 적으면 제자리로 갑니다" });
  return list;
}

function renderMain() {
  const main = $("#main");
  const cards = state.cards;
  if (!cards.length) {
    main.innerHTML = `<p class="empty">아직 비어 있어요.<br>위에서 어릴 적 좋아했던 것 하나를 찾아 담아 보세요.</p>`;
    return;
  }
  if (state.view === "timeline") {
    main.innerHTML = chapters(cards).map((ch) => `<section class="chapter">
      <div class="chapter-head"><h2>${esc(ch.name)}</h2><p>${esc(ch.range)}</p><p>${ch.cards.length}개</p></div>
      <div class="shelf-grid">${ch.cards.map(cardHTML).join("")}</div></section>`).join("");
  } else if (state.view === "shelf") {
    const pinned = cards.filter((c) => c.pinned);
    main.innerHTML = pinned.length
      ? chapters(pinned).map((ch) => `<section class="chapter">
          <div class="chapter-head"><h2>${esc(ch.name)}</h2><p>${esc(ch.range)}</p></div>
          <div class="shelf-grid">${ch.cards.map(cardHTML).join("")}</div></section>`).join("")
      : `<p class="empty">카드를 열어 ‘진열장에 놓기’를 켜면<br>시기별 대표작이 여기 모입니다.</p>`;
  } else {
    const kinds = Object.keys(KINDS).filter((k) => cards.some((c) => c.kind === k));
    const shown = cards.filter((c) => state.allKind === "all" || c.kind === state.allKind)
      .sort((a, b) => b.id - a.id);
    main.innerHTML = `<div class="toolbar">${["all", ...kinds].map((k) =>
      `<button class="chip ${state.allKind === k ? "on" : ""}" data-allk="${k}">${k === "all" ? "전체" : KINDS[k]} ${k === "all" ? cards.length : cards.filter((c) => c.kind === k).length}</button>`).join("")}</div>
      <div class="shelf-grid">${shown.map(cardHTML).join("")}</div>`;
  }
}

async function loadCards() {
  state.cards = await api("/api/cards");
  renderMain();
}

function renderWho() {
  const b = birthYear();
  $("#who").textContent = b
    ? `${state.settings.name ? state.settings.name + " · " : ""}${b}년생 · 담은 것 ${state.cards.length}개`
    : "출생연도를 알려 주면 나이 축 연대기를 그립니다";
}

// ── 이벤트 ───────────────────────────────────────────────
$("#search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("#q").value.trim();
  if (q) runSearch(q).catch((err) => ($("#result-grid").innerHTML = `<p class="errors">${esc(err.message)}</p>`));
});
$("#kind-chips").addEventListener("click", (e) => {
  const k = e.target.closest("[data-k]")?.dataset.k;
  if (k) { state.kindFilter = k; renderResults(); }
});
$("#result-grid").addEventListener("click", (e) => {
  const i = e.target.closest(".hit")?.dataset.i;
  if (i == null) return;
  const r = state.results[i];
  openEditor(findExisting(r) || fromHit(r));
});
$("#btn-manual").addEventListener("click", () => openEditor({ kind: "thing", title: $("#q").value.trim() }));
$("#btn-close-results").addEventListener("click", () => ($("#results").hidden = true));

$("#main").addEventListener("click", (e) => {
  const allk = e.target.closest("[data-allk]")?.dataset.allk;
  if (allk) { state.allKind = allk; renderMain(); return; }
  const id = e.target.closest(".card")?.dataset.id;
  if (!id) return;
  const card = state.cards.find((c) => c.id == id);
  card.kind === "memo" ? openMemo(card) : openEditor(card);
});

// ── 메모: 검색 없이 떠오른 걸 바로 적는 쪽지 ─────────────
let memoEditing = null;

function openMemo(card = {}) {
  memoEditing = card;
  const f = $("#memo-form");
  f.text.value = card.memory || "";
  f.met_year.value = card.met_year || "";
  f.pinned.checked = !!card.pinned;
  $("#memo-delete").hidden = !card.id;
  $("#memo").showModal();
  f.text.focus();
}

$("#btn-memo").addEventListener("click", () => openMemo());
$("#memo-cancel").addEventListener("click", () => $("#memo").close());
$("#memo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const text = f.text.value.trim();
  if (!text) return;
  const data = {
    kind: "memo", title: text.split("\n")[0].slice(0, 60), memory: text,
    met_year: f.met_year.value ? Number(f.met_year.value) : null, pinned: f.pinned.checked,
  };
  const id = memoEditing?.id;
  try {
    await api(id ? `/api/cards/${id}` : "/api/cards", { method: id ? "PUT" : "POST", body: JSON.stringify(data) });
  } catch (err) {
    alert(`메모를 저장하지 못했어요: ${err.message}`); // 창은 열어 두어 쓴 글을 잃지 않게
    return;
  }
  $("#memo").close();
  await loadCards();
  renderWho();
});
$("#memo-delete").addEventListener("click", async () => {
  if (!memoEditing?.id || !confirm("이 메모를 지울까요?")) return;
  await api(`/api/cards/${memoEditing.id}`, { method: "DELETE" });
  $("#memo").close();
  await loadCards();
  renderWho();
});
$("#views").addEventListener("click", (e) => {
  const v = e.target.closest("[data-view]")?.dataset.view;
  if (!v) return;
  state.view = v;
  document.querySelectorAll("#views button").forEach((b) => b.classList.toggle("on", b.dataset.view === v));
  renderMain();
});

$("#ed-met-year").addEventListener("input", (e) => {
  const a = ageOf(Number(e.target.value));
  $("#ed-age").value = a ?? "";
});
$("#ed-age").addEventListener("input", (e) => {
  if (birthYear() && e.target.value !== "") $("#ed-met-year").value = birthYear() + Number(e.target.value);
});
$("#ed-kind").addEventListener("change", (e) => {
  editing.kind = e.target.value;
  $("#ed-cover").innerHTML = cover({ ...editing, title: $("#ed-title").value }, { photoFirst: true });
});
$("#card-form").addEventListener("submit", (e) => {
  e.preventDefault();
  saveEditor().then(() => { $("#editor").close(); renderWho(); }).catch((err) => alert(err.message));
});
$("#ed-cancel").addEventListener("click", () => $("#editor").close());
$("#ed-delete").addEventListener("click", async () => {
  if (!editing?.id || !confirm(`‘${editing.title}’ 카드를 지울까요?`)) return;
  await api(`/api/cards/${editing.id}`, { method: "DELETE" });
  $("#editor").close();
  await loadCards();
  renderWho();
});

$("#btn-settings").addEventListener("click", openSettings);
function openSettings() {
  const f = $("#settings-form");
  f.birth_year.value = state.settings.birth_year || "";
  f.name.value = state.settings.name || "";
  $("#settings").showModal();
}
$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  state.settings = await api("/api/settings", { method: "PUT",
    body: JSON.stringify({ birth_year: f.birth_year.value, name: f.name.value }) });
  $("#settings").close();
  renderWho();
  renderMain();
});

(async function init() {
  state.settings = await api("/api/settings");
  await loadCards();
  renderWho();
  if (!birthYear()) openSettings();
})();
