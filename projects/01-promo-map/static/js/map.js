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

function initKakaoMap() {
    if (typeof kakao === 'undefined' || !kakao.maps) {
        // 카카오맵 SDK 로드 실패 → 폴백 메시지
        const mapEl = document.getElementById('kakaoMap');
        mapEl.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:0.9rem;text-align:center;padding:20px;">카카오맵 API 키를 설정해주세요<br><small>.env 파일의 KAKAO_MAP_API_KEY</small></div>';
        // 폴백: CSS 그리드 맵은 사용하지 않고 API만 동작
        loadNearbyStores();
        return;
    }

    const container = document.getElementById('kakaoMap');
    const options = {
        center: new kakao.maps.LatLng(userLat, userLon),
        level: 4,
    };
    kakaoMap = new kakao.maps.Map(container, options);

    // GPS 위치 감지
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
        const discBadge = disc ? `<span style="background:#FF3B30;color:white;border-radius:6px;padding:1px 5px;font-size:0.68rem;font-weight:700;">${disc.value}%</span>` : '';

        const content = `
            <div onclick="openStoreDetail(${store.id})" style="cursor:pointer;background:white;border-radius:12px;padding:5px 10px;box-shadow:0 2px 12px rgba(0,0,0,0.2);display:flex;align-items:center;gap:6px;white-space:nowrap;font-size:0.78rem;font-weight:600;border-left:3px solid ${store.icon_color};position:relative;">
                <div style="width:22px;height:22px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:12px;color:white;font-weight:700;background:${store.icon_color};">${store.icon_letter}</div>
                <span>${store.name.split(' ')[0]}</span>
                ${discBadge}
                <div style="position:absolute;bottom:-6px;left:50%;transform:translateX(-50%);border-left:6px solid transparent;border-right:6px solid transparent;border-top:6px solid white;"></div>
            </div>
        `;

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
        placeStoreMarkers(mapStores);
        renderPromoList(mapStores);
    } catch (e) {
        console.error('Nearby stores error:', e);
    }
}

function renderPromoList(stores) {
    const list = document.getElementById('promoList');
    const nearby = stores.filter(s => s.discounts && s.discounts.length > 0);

    document.getElementById('promoTitle').textContent = `주변 할인 혜택 ${nearby.length}건`;
    document.getElementById('promoSubtitle').textContent = '임직원 전용 할인';

    if (nearby.length === 0) {
        list.innerHTML = '<div class="loading-text">주변에 할인 매장이 없습니다</div>';
        return;
    }

    list.innerHTML = nearby.map(s => {
        const d = s.discounts[0];
        return `<div class="promo-item" onclick="openStoreDetail(${s.id})">
            <div class="store-info">
                <div class="s-icon" style="background:${s.icon_color}">${s.icon_letter}</div>
                <div>
                    <div class="s-name">${s.name}</div>
                    <div class="s-dist">${s.distance_m}m | ${s.brand}</div>
                </div>
            </div>
            <div class="discount">${d.value}% OFF</div>
        </div>`;
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
        ? '★'.repeat(Math.round(store.avg_rating)) + '☆'.repeat(5 - Math.round(store.avg_rating))
        : '리뷰 없음';

    let discountsHtml = '';
    if (store.discounts && store.discounts.length > 0) {
        discountsHtml = store.discounts.map(d =>
            `<div class="discount-item">
                <span class="disc-desc">${d.description}</span>
                <span class="disc-badge">${d.value}%</span>
            </div>`
        ).join('');
    } else {
        discountsHtml = '<div class="empty-state">현재 활성 할인이 없습니다</div>';
    }

    const favBtnClass = store.is_favorited ? 'fav-toggle active' : 'fav-toggle';
    const favBtnText = store.is_favorited ? '♥ 즐겨찾기 해제' : '♡ 즐겨찾기 추가';

    document.getElementById('modalStoreBody').innerHTML = `
        <div class="detail-header">
            <div class="detail-icon" style="background:${store.icon_color}">${store.icon_letter}</div>
            <div class="detail-info">
                <h4>${store.brand}</h4>
                <p>${store.address || store.category}</p>
                ${store.phone ? `<p>📞 ${store.phone}</p>` : ''}
            </div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <span style="color:#FFB800">${reviewStars} (${store.reviews_count || 0})</span>
            ${API.isLoggedIn() ? `<button class="${favBtnClass}" onclick="toggleFavorite(${store.id}, this)">${favBtnText}</button>` : ''}
        </div>
        <div class="detail-section">
            <h5>할인 혜택</h5>
            ${discountsHtml}
        </div>
        <div class="detail-section">
            <h5>리뷰 (${store.reviews_count || 0})</h5>
            <div id="storeReviews"><div class="loading-text">리뷰 로딩 중...</div></div>
            ${API.isLoggedIn() ? `
            <div class="review-form">
                <div class="star-rating" id="starRating">
                    ${[1,2,3,4,5].map(i => `<span data-rating="${i}" onclick="setRating(${i})">☆</span>`).join('')}
                </div>
                <div class="form-group" style="margin-bottom:8px;">
                    <textarea id="reviewContent" rows="2" placeholder="리뷰를 작성해주세요..." style="width:100%;padding:8px;border:1px solid #ddd;border-radius:8px;font-size:0.85rem;"></textarea>
                </div>
                <button class="btn-primary" onclick="submitReview(${store.id})" style="font-size:0.85rem;padding:8px 16px;">리뷰 작성</button>
            </div>` : ''}
        </div>
    `;

    // 리뷰 로드
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
        el.innerHTML = data.items.map(r => `
            <div class="review-item">
                <div class="review-header">
                    <span class="review-user">${r.user_name}</span>
                    <span class="review-date">${r.created_at ? r.created_at.split('T')[0] : ''}</span>
                </div>
                <div class="review-rating">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</div>
                ${r.content ? `<div class="review-content">${r.content}</div>` : ''}
            </div>
        `).join('');
    } catch {
        document.getElementById('storeReviews').innerHTML = '<div class="empty-state">리뷰를 불러올 수 없습니다</div>';
    }
}

let selectedRating = 0;
function setRating(rating) {
    selectedRating = rating;
    document.querySelectorAll('#starRating span').forEach((el, i) => {
        el.textContent = i < rating ? '★' : '☆';
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
        document.querySelectorAll('#starRating span').forEach(el => { el.textContent = '☆'; el.classList.remove('active'); });
    } catch (err) {
        showToast(err.detail || '리뷰 작성 실패');
    }
}

async function toggleFavorite(storeId, btn) {
    try {
        if (btn.classList.contains('active')) {
            await API.removeFavorite(storeId);
            btn.classList.remove('active');
            btn.textContent = '♡ 즐겨찾기 추가';
            showToast('즐겨찾기 해제');
        } else {
            await API.addFavorite(storeId);
            btn.classList.add('active');
            btn.textContent = '♥ 즐겨찾기 해제';
            showToast('즐겨찾기 추가');
        }
    } catch (err) {
        showToast(err.detail || '처리 실패');
    }
}

function closeStoreModal() {
    document.getElementById('storeModal').style.display = 'none';
}
