/**
 * PromoMap 검색 탭
 * - 디바운스 검색 제안
 * - 최근 검색어 (localStorage)
 * - 카테고리 배지, 전화번호, 도보시간 표시
 */

let searchPage = 1;
let searchDebounceTimer = null;
const RECENT_SEARCHES_KEY = 'pm_recent_searches';
const MAX_RECENT_SEARCHES = 8;

/**
 * 최근 검색어 관리
 */
function getRecentSearches() {
    try {
        const data = localStorage.getItem(RECENT_SEARCHES_KEY);
        return data ? JSON.parse(data) : [];
    } catch {
        return [];
    }
}

function addRecentSearch(query) {
    if (!query || query.trim() === '') return;
    const q = query.trim();
    let recent = getRecentSearches();
    recent = recent.filter(r => r !== q);
    recent.unshift(q);
    if (recent.length > MAX_RECENT_SEARCHES) {
        recent = recent.slice(0, MAX_RECENT_SEARCHES);
    }
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(recent));
}

function removeRecentSearch(query) {
    let recent = getRecentSearches();
    recent = recent.filter(r => r !== query);
    localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(recent));
}

/**
 * 검색 제안 드롭다운 렌더링
 */
function showSearchSuggestions(items, query) {
    const suggestionsEl = document.getElementById('searchSuggestions');
    if (!suggestionsEl) return;

    let html = '';
    const recent = getRecentSearches();

    // 최근 검색어 표시 (검색어가 비어있거나 포커스 시)
    if (!query || query.trim() === '') {
        if (recent.length > 0) {
            html += '<div class="suggestion-section">';
            html += '<div class="suggestion-section-title">최근 검색</div>';
            html += recent.map(r =>
                '<div class="suggestion-item" onclick="selectSuggestion(\'' + escapeHtml(r) + '\')">'
                + '<span class="suggestion-icon">\uD83D\uDD52</span>'
                + '<span class="suggestion-text">' + escapeHtml(r) + '</span>'
                + '<span class="suggestion-remove" onclick="event.stopPropagation(); removeRecentAndRefresh(\'' + escapeHtml(r) + '\')">\u2715</span>'
                + '</div>'
            ).join('');
            html += '</div>';
        }
    }

    // 검색 결과 제안
    if (items && items.length > 0) {
        html += '<div class="suggestion-section">';
        html += '<div class="suggestion-section-title">검색 제안</div>';
        html += items.slice(0, 6).map(s => {
            const catInfo = getCategoryInfo(s.category);
            return '<div class="suggestion-item" onclick="selectSuggestion(\'' + escapeHtml(s.name) + '\')">'
                + '<span class="suggestion-icon">' + catInfo.icon + '</span>'
                + '<span class="suggestion-text">' + escapeHtml(s.name) + ' <span style="color:#999;font-size:0.78rem;">' + escapeHtml(s.brand) + '</span></span>'
                + '</div>';
        }).join('');
        html += '</div>';
    }

    if (html) {
        suggestionsEl.innerHTML = html;
        suggestionsEl.style.display = 'block';
    } else {
        suggestionsEl.style.display = 'none';
    }
}

function hideSuggestions() {
    const el = document.getElementById('searchSuggestions');
    if (el) el.style.display = 'none';
}

function selectSuggestion(text) {
    const input = document.getElementById('searchInput');
    input.value = text;
    hideSuggestions();
    if (getCurrentTab() !== 'search') switchTab('search');
    addRecentSearch(text);
    performSearch(text);
}

function removeRecentAndRefresh(query) {
    removeRecentSearch(query);
    showSearchSuggestions(null, '');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML.replace(/'/g, "\\'");
}

/**
 * 디바운스 검색 제안 요청
 */
function debouncedSuggest(query) {
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);

    if (!query || query.trim().length < 1) {
        showSearchSuggestions(null, '');
        return;
    }

    searchDebounceTimer = setTimeout(async () => {
        try {
            const data = await API.searchStores(query.trim(), 1);
            showSearchSuggestions(data.items || [], query.trim());
        } catch {
            showSearchSuggestions([], query.trim());
        }
    }, 300);
}

/**
 * 검색 실행
 */
async function performSearch(query, page) {
    if (page === undefined) page = 1;
    const container = document.getElementById('searchResults');
    if (!query || query.trim() === '') {
        container.innerHTML = '<div class="empty-state">매장을 검색해보세요</div>';
        return;
    }

    container.innerHTML = '<div class="loading-text">검색 중...</div>';

    try {
        const data = await API.searchStores(query, page);
        searchPage = page;

        if (!data.items || data.items.length === 0) {
            container.innerHTML = '<div class="empty-state">'
                + '"' + escapeHtml(query) + '" 검색 결과가 없습니다'
                + '<div class="empty-suggestion">다른 키워드로 검색하거나, 브랜드명/카테고리로 검색해보세요</div>'
                + '</div>';
            return;
        }

        let html = '<div style="padding:0 0 8px;color:#666;font-size:0.8rem;">총 ' + data.total + '개 결과</div>';
        html += data.items.map(s => {
            const catInfo = getCategoryInfo(s.category);
            const walkTime = s.distance_m ? getWalkingTime(s.distance_m) : '';
            const phoneLine = s.phone
                ? '<a href="tel:' + s.phone + '" class="card-phone" onclick="event.stopPropagation();">\uD83D\uDCDE ' + s.phone + '</a>'
                : '';

            return '<div class="store-card" onclick="openStoreDetail(' + s.id + ')">'
                + '<div class="card-icon" style="background:' + s.icon_color + '">'
                + s.icon_letter
                + '<span class="card-category-icon">' + catInfo.icon + '</span>'
                + '</div>'
                + '<div class="card-info">'
                + '<div class="card-name">' + s.name + '</div>'
                + '<div class="card-meta">'
                + '<span class="category-badge">' + catInfo.icon + ' ' + catInfo.label + '</span> '
                + s.brand
                + (walkTime ? ' · ' + walkTime : '')
                + '</div>'
                + (phoneLine ? '<div>' + phoneLine + '</div>' : '')
                + '</div>'
                + '</div>';
        }).join('');

        // 페이지네이션
        if (data.pages > 1) {
            html += '<div style="display:flex;justify-content:center;gap:8px;padding:16px 0;">';
            if (page > 1) {
                html += '<button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="performSearch(\'' + escapeHtml(query) + '\',' + (page-1) + ')">이전</button>';
            }
            html += '<span style="padding:6px 12px;color:#666;font-size:0.85rem;">' + page + ' / ' + data.pages + '</span>';
            if (page < data.pages) {
                html += '<button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="performSearch(\'' + escapeHtml(query) + '\',' + (page+1) + ')">다음</button>';
            }
            html += '</div>';
        }

        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div class="empty-state">검색에 실패했습니다</div>';
    }
}

function initSearch() {
    const input = document.getElementById('searchInput');
    const btn = document.getElementById('searchBtn');

    btn.addEventListener('click', () => {
        const query = input.value.trim();
        hideSuggestions();
        if (getCurrentTab() !== 'search') switchTab('search');
        addRecentSearch(query);
        performSearch(query);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const query = input.value.trim();
            hideSuggestions();
            if (getCurrentTab() !== 'search') switchTab('search');
            addRecentSearch(query);
            performSearch(query);
        }
    });

    // 입력 시 디바운스 제안
    input.addEventListener('input', (e) => {
        debouncedSuggest(e.target.value);
    });

    // 포커스 시 최근 검색어 표시
    input.addEventListener('focus', () => {
        const query = input.value.trim();
        if (!query) {
            showSearchSuggestions(null, '');
        } else {
            debouncedSuggest(query);
        }
    });

    // 바깥 클릭 시 제안 닫기
    document.addEventListener('click', (e) => {
        const wrapper = document.getElementById('searchWrapper');
        if (wrapper && !wrapper.contains(e.target)) {
            hideSuggestions();
        }
    });
}
