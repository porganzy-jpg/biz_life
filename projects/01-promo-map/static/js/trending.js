/**
 * PromoMap - 트렌딩/인기 할인 UI
 * 인기 할인 캐러셀, 인기 매장 섹션, 인기순 정렬
 */

let trendingLoaded = false;

/**
 * 트렌딩 데이터 로드 및 렌더링 (앱 시작 시 1회 호출)
 */
async function loadTrending() {
    if (trendingLoaded) return;
    trendingLoaded = true;

    // 각 섹션 독립적으로 로드하여 부분 실패 허용
    try {
        var trendingRes = await API.getTrendingDiscounts(7, 10);
        renderTrendingCarousel(trendingRes.items || []);
    } catch (e) {
        console.warn('Trending discounts load failed:', e);
        var trendingSec = document.getElementById('trendingSection');
        if (trendingSec) {
            var trendingCarousel = document.getElementById('trendingCarousel');
            if (trendingCarousel) {
                trendingCarousel.innerHTML = '<div class="empty-state" style="padding:20px;font-size:0.85rem;">인기 할인을 불러올 수 없습니다</div>';
            }
        }
    }

    try {
        var popularRes = await API.getPopularStores(8);
        renderPopularStores(popularRes.items || []);
    } catch (e) {
        console.warn('Popular stores load failed:', e);
        var popularList = document.getElementById('popularStoresList');
        if (popularList) {
            popularList.innerHTML = '<div class="empty-state" style="padding:20px;font-size:0.85rem;">인기 매장을 불러올 수 없습니다</div>';
        }
    }

    try {
        var hotDealsRes = await API.getHotDeals(5);
        renderHotDeals(hotDealsRes.items || []);
    } catch (e) {
        console.warn('Hot deals load failed:', e);
        var hotDealsList = document.getElementById('hotDealsList');
        if (hotDealsList) {
            hotDealsList.innerHTML = '<div class="empty-state" style="padding:20px;font-size:0.85rem;">핫딜을 불러올 수 없습니다</div>';
        }
    }
}

/**
 * 인기 할인 캐러셀 렌더링
 */
function renderTrendingCarousel(items) {
    const container = document.getElementById('trendingCarousel');
    if (!container) return;

    if (!items || items.length === 0) {
        container.closest('.trending-section').style.display = 'none';
        return;
    }

    container.innerHTML = items.map(function(item, idx) {
        var rankBadge = idx < 3
            ? '<span class="trending-rank trending-rank-top">' + (idx + 1) + '</span>'
            : '<span class="trending-rank">' + (idx + 1) + '</span>';

        var usageBadge = '<span class="usage-badge">' + item.usage_count + '\uBA85 \uC774\uC6A9</span>';

        var expiryHtml = '';
        if (typeof getExpiryBadgeHtml === 'function') {
            expiryHtml = getExpiryBadgeHtml(item.valid_until);
        }

        return '<div class="trending-card" onclick="openStoreDetail(' + item.store_id + ')">'
            + rankBadge
            + '<div class="trending-card-icon" style="background:' + item.icon_color + '">'
            + item.icon_letter
            + '</div>'
            + '<div class="trending-card-body">'
            + '<div class="trending-card-name">' + item.store_name + '</div>'
            + '<div class="trending-card-desc">' + item.description + '</div>'
            + '<div class="trending-card-meta">'
            + '<span class="trending-discount-badge">' + item.discount_value + '% OFF</span> '
            + usageBadge
            + expiryHtml
            + '</div>'
            + '</div>'
            + '</div>';
    }).join('');
}

/**
 * 인기 매장 섹션 렌더링
 */
function renderPopularStores(items) {
    var container = document.getElementById('popularStoresList');
    if (!container) return;

    if (!items || items.length === 0) {
        container.closest('.popular-stores-section').style.display = 'none';
        return;
    }

    container.innerHTML = items.map(function(item) {
        var stars = '';
        if (item.avg_rating > 0) {
            var full = Math.round(item.avg_rating);
            stars = '\u2605'.repeat(full) + '\u2606'.repeat(5 - full);
        } else {
            stars = '\uB9AC\uBDF0 \uC5C6\uC74C';
        }

        var catInfo = (typeof getCategoryInfo === 'function')
            ? getCategoryInfo(item.category)
            : { icon: '', label: item.category || '' };

        var usageText = item.usage_count > 0
            ? '<span class="usage-badge-sm">' + item.usage_count + '\uBA85 \uC774\uC6A9</span>'
            : '';

        return '<div class="popular-store-card" onclick="openStoreDetail(' + item.store_id + ')">'
            + '<div class="popular-store-icon" style="background:' + item.icon_color + '">'
            + item.icon_letter
            + '</div>'
            + '<div class="popular-store-info">'
            + '<div class="popular-store-name">'
            + '<span class="category-badge">' + catInfo.icon + '</span> '
            + item.name
            + '</div>'
            + '<div class="popular-store-meta">'
            + '<span class="popular-store-rating" style="color:#FFB800">' + stars + '</span>'
            + ' <span style="color:#999;font-size:0.75rem;">(' + (item.review_count || 0) + ')</span>'
            + '</div>'
            + '<div class="popular-store-meta">'
            + item.brand + ' ' + usageText
            + '</div>'
            + '</div>'
            + '</div>';
    }).join('');
}

/**
 * 핫딜 섹션 렌더링
 */
function renderHotDeals(items) {
    var container = document.getElementById('hotDealsList');
    if (!container) return;

    if (!items || items.length === 0) {
        container.closest('.hot-deals-section').style.display = 'none';
        return;
    }

    container.innerHTML = items.map(function(item) {
        var velocityText = Number(item.velocity).toLocaleString() + '\uC6D0/\uC77C';

        return '<div class="hot-deal-card" onclick="openStoreDetail(' + item.store_id + ')">'
            + '<div class="hot-deal-icon" style="background:' + item.icon_color + '">'
            + item.icon_letter
            + '</div>'
            + '<div class="hot-deal-info">'
            + '<div class="hot-deal-name">' + item.store_name + '</div>'
            + '<div class="hot-deal-desc">' + item.description + '</div>'
            + '</div>'
            + '<div class="hot-deal-stats">'
            + '<div class="hot-deal-discount">' + item.discount_value + '%</div>'
            + '<div class="hot-deal-velocity">\u26A1 ' + velocityText + '</div>'
            + '</div>'
            + '</div>';
    }).join('');
}

/**
 * 인기순 정렬 함수 - 프로모 리스트에서 사용
 * mapStores에 usage_count가 있으면 해당 값을 기준으로 정렬
 */
function sortByPopularity(stores) {
    var sorted = stores.slice();
    sorted.sort(function(a, b) {
        return (b.usage_count || 0) - (a.usage_count || 0);
    });
    return sorted;
}
