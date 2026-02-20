/**
 * PromoMap 카카오맵 관리
 */
let kakaoMap = null;
let mapMarkers = [];
let mapOverlays = [];
let userMarker = null;
let radiusCircle = null;
let userLat = 37.5005, userLon = 127.0365;
let mapStores = [];
let activeCategoryFilter = 'all';

// 카테고리 설정
const CATEGORY_MAP = {
    food: { label: '음식점', icon: '\uD83C\uDF5C' },
    cafe: { label: '카페', icon: '\u2615' },
    shopping: { label: '쇼핑', icon: '\uD83D\uDECD\uFE0F' },
    convenience: { label: '편의점', icon: '\uD83C\uDFEA' },
    entertainment: { label: '엔터', icon: '\uD83C\uDFAC' },
    general: { label: '기타', icon: '\uD83C\uDFE2' },
};

function getCategoryInfo(category) {
    return CATEGORY_MAP[category] || CATEGORY_MAP['general'];
}

/**
 * 할인 만료일까지 남은 일수 계산
 */
function getDaysRemaining(validUntil) {
    if (!validUntil) return null;
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const end = new Date(validUntil);
    end.setHours(0, 0, 0, 0);
    const diffMs = end - now;
    return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

/**
 * 할인 만료 배지 HTML 생성
 */
function getExpiryBadgeHtml(validUntil) {
    const days = getDaysRemaining(validUntil);
    if (days === null || days > 7) return '';
    if (days <= 0) return '<span class="expiry-badge expiry-urgent">만료됨</span>';
    const cls = days <= 3 ? 'expiry-urgent' : 'expiry-warning';
    return '<span class="expiry-badge ' + cls + '">D-' + days + '</span>';
}

/**
 * 거리 → 도보 시간 계산 (80m/분)
 */
function getWalkingTime(distanceM) {
    if (!distanceM && distanceM !== 0) return '';
    const minutes = Math.ceil(distanceM / 80);
    if (minutes < 1) return '1분 미만';
    return '도보 ' + minutes + '분';
}

function initKakaoMap() {
    if (typeof kakao === 'undefined' || !kakao.maps) {
        const mapEl = document.getElementById('kakaoMap');
        mapEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:0.9rem;text-align:center;padding:20px;">카카오맵 API 키를 설정해주세요<br><small>.env 파일의 KAKAO_MAP_API_KEY</small></div>';
        loadNearbyStores();
        return;
    }

    const container = document.getElementById('kakaoMap');
    const options = {
        center: new kakao.maps.LatLng(userLat, userLon),
        level: 4,
    };
    kakaoMap = new kakao.maps.Map(container, options);

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => {
                userLat = pos.coords.latitude;
                userLon = pos.coords.longitude;
                const loc = new kakao.maps.LatLng(userLat, userLon);
                kakaoMap.setCenter(loc);
                placeUserMarker(loc);
                drawRadiusCircle(loc);
                loadNearbyStores();
            },
            () => {
                const loc = new kakao.maps.LatLng(userLat, userLon);
                placeUserMarker(loc);
                drawRadiusCircle(loc);
                loadNearbyStores();
            },
            { enableHighAccuracy: true, timeout: 5000 }
        );
    } else {
        const loc = new kakao.maps.LatLng(userLat, userLon);
        placeUserMarker(loc);
        drawRadiusCircle(loc);
        loadNearbyStores();
    }

    // 카테고리 필터 초기화
    initCategoryFilter();
}

function initCategoryFilter() {
    const chips = document.querySelectorAll('.category-chip');
    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            chips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            activeCategoryFilter = chip.dataset.category;
            applyFilterAndRender();
        });
    });
}

function applyFilterAndRender() {
    const filtered = getFilteredStores(mapStores);
    placeStoreMarkers(filtered);
    renderPromoList(filtered);
}

function getFilteredStores(stores) {
    if (activeCategoryFilter === 'all') return stores;
    return stores.filter(s => s.category === activeCategoryFilter);
}

function placeUserMarker(position) {
    if (!kakaoMap) return;
    if (userMarker) userMarker.setMap(null);

    const content = '<div style="width:20px;height:20px;background:#4285f4;border:3px solid white;border-radius:50%;box-shadow:0 0 0 8px rgba(66,133,244,0.2);animation:pulse 2s infinite;"></div>';
    userMarker = new kakao.maps.CustomOverlay({
        position: position,
        content: content,
        yAnchor: 0.5,
        xAnchor: 0.5,
        zIndex: 100,
    });
    userMarker.setMap(kakaoMap);
}

function drawRadiusCircle(center) {
    if (!kakaoMap) return;
    if (radiusCircle) radiusCircle.setMap(null);

    radiusCircle = new kakao.maps.Circle({
        center: center,
        radius: 100,
        strokeWeight: 2,
        strokeColor: '#4285f4',
        strokeOpacity: 0.4,
        strokeStyle: 'dash',
        fillColor: '#4285f4',
        fillOpacity: 0.05,
    });
    radiusCircle.setMap(kakaoMap);
}

function clearMapMarkers() {
    mapMarkers.forEach(m => m.setMap(null));
    mapOverlays.forEach(o => o.setMap(null));
    mapMarkers = [];
    mapOverlays = [];
}

function placeStoreMarkers(stores) {
    if (!kakaoMap) return;
    clearMapMarkers();

    stores.forEach(store => {
        const position = new kakao.maps.LatLng(store.latitude, store.longitude);
        const disc = store.discounts && store.discounts.length > 0 ? store.discounts[0] : null;
        let discBadge = '';
        if (disc) {
            const expiryHtml = getExpiryBadgeHtml(disc.valid_until);
            discBadge = '<span style="background:#FF3B30;color:white;border-radius:6px;padding:1px 5px;font-size:0.68rem;font-weight:700;">' + disc.value + '%</span>';
            if (expiryHtml) {
                discBadge += ' ' + expiryHtml;
            }
        }

        const content = '<div onclick="openStoreDetail(' + store.id + ')" style="cursor:pointer;background:white;border-radius:12px;padding:5px 10px;box-shadow:0 2px 12px rgba(0,0,0,0.2);display:flex;align-items:center;gap:6px;white-space:nowrap;font-size:0.78rem;font-weight:600;border-left:3px solid ' + store.icon_color + ';position:relative;">'
                + '<div style="width:22px;height:22px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:12px;color:white;font-weight:700;background:' + store.icon_color + ';">' + store.icon_letter + '</div>'
                + '<span>' + store.name.split(' ')[0] + '</span>'
                + discBadge
                + '<div style="position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);border-left:6px solid transparent;border-right:6px solid transparent;border-top:6px solid white;"></div>'
            + '</div>';

        const overlay = new kakao.maps.CustomOverlay({
            position: position,
            content: content,
            yAnchor: 1.3,
            zIndex: 90,
        });
        overlay.setMap(kakaoMap);
        mapOverlays.push(overlay);
    });
}

async function loadNearbyStores() {
    try {
        const data = await API.getNearby(userLat, userLon, 200);
        mapStores = data.stores || [];
        applyFilterAndRender();
    } catch (e) {
        console.error('Nearby stores error:', e);
    }
}

function renderPromoList(stores) {
    const list = document.getElementById('promoList');
    const nearby = stores.filter(s => s.discounts && s.discounts.length > 0);

    document.getElementById('promoTitle').textContent = '주변 할인 혜택 ' + nearby.length + '건';
    document.getElementById('promoSubtitle').textContent = '임직원 전용 할인';

    if (nearby.length === 0) {
        list.innerHTML = '<div class="loading-text">주변에 할인 매장이 없습니다</div>';
        return;
    }

    list.innerHTML = nearby.map(s => {
        const d = s.discounts[0];
        const catInfo = getCategoryInfo(s.category);
        const walkTime = getWalkingTime(s.distance_m);
        const expiryHtml = getExpiryBadgeHtml(d.valid_until);
        const phoneHtml = s.phone ? '<span style="color:#4285f4;font-size:0.7rem;">\uD83D\uDCDE ' + s.phone + '</span>' : '';

        return '<div class="promo-item" onclick="openStoreDetail(' + s.id + ')">'
            + '<div class="store-info">'
            + '  <div class="s-icon" style="background:' + s.icon_color + '">' + s.icon_letter + '</div>'
            + '  <div>'
            + '    <div class="s-name">'
            + '      <span class="category-badge">' + catInfo.icon + ' ' + catInfo.label + '</span> '
            +        s.name
            + '    </div>'
            + '    <div class="s-dist">' + s.distance_m + 'm'
            +        (walkTime ? ' · ' + walkTime : '')
            +        ' | ' + s.brand
            + '    </div>'
            + (phoneHtml ? '<div>' + phoneHtml + '</div>' : '')
            + '  </div>'
            + '</div>'
            + '<div class="discount-wrap">'
            + '  <div class="discount">' + d.value + '% OFF</div>'
            + (expiryHtml ? expiryHtml : '')
            + '</div>'
            + '</div>';
    }).join('');
}

async function openStoreDetail(storeId) {
    try {
        const store = await API.getStoreDetail(storeId);
        renderStoreModal(store);
        document.getElementById('storeModal').style.display = 'flex';
    } catch (e) {
        showToast('매장 정보를 불러올 수 없습니다');
    }
}

function renderStoreModal(store) {
    document.getElementById('modalStoreName').textContent = store.name;

    const reviewStars = store.avg_rating
        ? '\u2605'.repeat(Math.round(store.avg_rating)) + '\u2606'.repeat(5 - Math.round(store.avg_rating))
        : '리뷰 없음';

    const catInfo = getCategoryInfo(store.category);

    let discountsHtml = '';
    if (store.discounts && store.discounts.length > 0) {
        discountsHtml = store.discounts.map(d => {
            const expiryHtml = getExpiryBadgeHtml(d.valid_until);
            return '<div class="discount-item">'
                + '<span class="disc-desc">' + d.description + '</span>'
                + '<div style="display:flex;align-items:center;gap:6px;">'
                + (expiryHtml ? expiryHtml : '')
                + '<span class="disc-badge">' + d.value + '%</span>'
                + '</div>'
                + '</div>';
        }).join('');
    } else {
        discountsHtml = '<div class="empty-state">현재 활성 할인이 없습니다</div>';
    }

    const favBtnClass = store.is_favorited ? 'fav-toggle active' : 'fav-toggle';
    const favBtnText = store.is_favorited ? '\u2665 즐겨찾기 해제' : '\u2661 즐겨찾기 추가';

    const phoneHtml = store.phone
        ? '<p><a href="tel:' + store.phone + '" class="phone-link">\uD83D\uDCDE ' + store.phone + '</a></p>'
        : '';

    document.getElementById('modalStoreBody').innerHTML =
        '<div class="detail-header">'
        + '<div class="detail-icon" style="background:' + store.icon_color + '">' + store.icon_letter + '</div>'
        + '<div class="detail-info">'
        + '  <h4>' + store.brand + ' <span class="category-badge">' + catInfo.icon + ' ' + catInfo.label + '</span></h4>'
        + '  <p>' + (store.address || store.category) + '</p>'
        + phoneHtml
        + '</div>'
        + '</div>'
        + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
        + '<span style="color:#FFB800">' + reviewStars + ' (' + (store.reviews_count || 0) + ')</span>'
        + (API.isLoggedIn() ? '<button class="' + favBtnClass + '" onclick="toggleFavorite(' + store.id + ', this)">' + favBtnText + '</button>' : '')
        + '</div>'
        + '<div class="detail-section">'
        + '<h5>할인 혜택</h5>'
        + discountsHtml
        + '</div>'
        + '<div class="detail-section">'
        + '<h5>리뷰 (' + (store.reviews_count || 0) + ')</h5>'
        + '<div id="storeReviews"><div class="loading-text">리뷰 로딩 중...</div></div>'
        + (API.isLoggedIn() ?
            '<div class="review-form">'
            + '<div class="star-rating" id="starRating">'
            + [1,2,3,4,5].map(i => '<span data-rating="' + i + '" onclick="setRating(' + i + ')">\u2606</span>').join('')
            + '</div>'
            + '<div class="form-group" style="margin-bottom:8px;">'
            + '<textarea id="reviewContent" rows="2" placeholder="리뷰를 작성해주세요..." style="width:100%;padding:8px;border:1px solid #ddd;border-radius:8px;font-size:0.85rem;"></textarea>'
            + '</div>'
            + '<button class="btn-primary" onclick="submitReview(' + store.id + ')" style="font-size:0.85rem;padding:8px 16px;">리뷰 작성</button>'
            + '</div>' : '')
        + '</div>';

    loadStoreReviews(store.id);
}

async function loadStoreReviews(storeId) {
    try {
        const data = await API.getReviews(storeId);
        const el = document.getElementById('storeReviews');
        if (!data.items || data.items.length === 0) {
            el.innerHTML = '<div class="empty-state">아직 리뷰가 없습니다</div>';
            return;
        }
        el.innerHTML = data.items.map(r =>
            '<div class="review-item">'
            + '<div class="review-header">'
            + '  <span class="review-user">' + r.user_name + '</span>'
            + '  <span class="review-date">' + (r.created_at ? r.created_at.split('T')[0] : '') + '</span>'
            + '</div>'
            + '<div class="review-rating">' + '\u2605'.repeat(r.rating) + '\u2606'.repeat(5-r.rating) + '</div>'
            + (r.content ? '<div class="review-content">' + r.content + '</div>' : '')
            + '</div>'
        ).join('');
    } catch {
        document.getElementById('storeReviews').innerHTML = '<div class="empty-state">리뷰를 불러올 수 없습니다</div>';
    }
}

let selectedRating = 0;
function setRating(rating) {
    selectedRating = rating;
    document.querySelectorAll('#starRating span').forEach((el, i) => {
        el.textContent = i < rating ? '\u2605' : '\u2606';
        el.classList.toggle('active', i < rating);
    });
}

async function submitReview(storeId) {
    if (selectedRating === 0) { showToast('별점을 선택해주세요'); return; }
    const content = document.getElementById('reviewContent').value;
    try {
        await API.createReview({ store_id: storeId, rating: selectedRating, content });
        showToast('리뷰가 등록되었습니다');
        loadStoreReviews(storeId);
        selectedRating = 0;
        document.getElementById('reviewContent').value = '';
        document.querySelectorAll('#starRating span').forEach(el => { el.textContent = '\u2606'; el.classList.remove('active'); });
    } catch (err) {
        showToast(err.detail || '리뷰 작성 실패');
    }
}

async function toggleFavorite(storeId, btn) {
    try {
        if (btn.classList.contains('active')) {
            await API.removeFavorite(storeId);
            btn.classList.remove('active');
            btn.textContent = '\u2661 즐겨찾기 추가';
            showToast('즐겨찾기 해제');
        } else {
            await API.addFavorite(storeId);
            btn.classList.add('active');
            btn.textContent = '\u2665 즐겨찾기 해제';
            showToast('즐겨찾기 추가');
        }
    } catch (err) {
        showToast(err.detail || '처리 실패');
    }
}

function closeStoreModal() {
    document.getElementById('storeModal').style.display = 'none';
}
