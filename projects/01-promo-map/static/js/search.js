/**
 * PromoMap 검색 탭
 */

let searchPage = 1;

async function performSearch(query, page = 1) {
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
            container.innerHTML = `<div class="empty-state">"${query}" 검색 결과가 없습니다</div>`;
            return;
        }

        let html = `<div style="padding:0 0 8px;color:#666;font-size:0.8rem;">총 ${data.total}개 결과</div>`;
        html += data.items.map(s => `
            <div class="store-card" onclick="openStoreDetail(${s.id})">
                <div class="card-icon" style="background:${s.icon_color}">${s.icon_letter}</div>
                <div class="card-info">
                    <div class="card-name">${s.name}</div>
                    <div class="card-meta">${s.brand} · ${s.category}</div>
                </div>
            </div>
        `).join('');

        // 페이지네이션
        if (data.pages > 1) {
            html += '<div style="display:flex;justify-content:center;gap:8px;padding:16px 0;">';
            if (page > 1) {
                html += `<button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="performSearch('${query}',${page-1})">이전</button>`;
            }
            html += `<span style="padding:6px 12px;color:#666;font-size:0.85rem;">${page} / ${data.pages}</span>`;
            if (page < data.pages) {
                html += `<button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="performSearch('${query}',${page+1})">다음</button>`;
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
        if (getCurrentTab() !== 'search') switchTab('search');
        performSearch(query);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const query = input.value.trim();
            if (getCurrentTab() !== 'search') switchTab('search');
            performSearch(query);
        }
    });
}
