/**
 * HomeFinder - 카카오맵 매물 지도
 */

const MAP_API = '/api/v1/dashboard/map-markers';

// XSS 방지 HTML 이스케이프
function esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
let map = null;
let markers = [];
let clusterer = null;
let infowindow = null;
let _lastFilteredData = [];
let _mapSortAsc = false;

// ──────── 마커 SVG 생성 ────────

function _scoreColor(score) {
    if (score >= 80) return '#198754';
    if (score >= 60) return '#0d6efd';
    if (score >= 40) return '#fd7e14';
    return '#dc3545';
}

function makeScoreMarkerSVG(score, isCandidate, isLand) {
    const s = Math.round(score || 0);
    const color = isCandidate ? '#e07a5f' : isLand ? '#198754' : _scoreColor(s);
    const star = isCandidate ? '<text x="16" y="8" text-anchor="middle" font-size="8" fill="white">★</text>' : '';
    return 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="44" viewBox="0 0 32 44">` +
        `<path d="M16 0C7.2 0 0 7.2 0 16c0 12 16 28 16 28s16-16 16-28C32 7.2 24.8 0 16 0z" fill="${color}"/>` +
        `<circle cx="16" cy="15" r="11" fill="white"/>` +
        `<text x="16" y="20" text-anchor="middle" font-size="12" font-weight="bold" fill="${color}">${s}</text>` +
        star + `</svg>`
    );
}

function makeTxSummaryMarkerSVG(count) {
    const label = count > 999 ? Math.round(count / 100) / 10 + 'k' : count;
    return 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="44" height="52" viewBox="0 0 44 52">` +
        `<path d="M22 0C10 0 0 10 0 22c0 16 22 30 22 30s22-14 22-30C44 10 34 0 22 0z" fill="#7b2d8e" opacity="0.85"/>` +
        `<circle cx="22" cy="20" r="14" fill="white"/>` +
        `<text x="22" y="18" text-anchor="middle" font-size="9" font-weight="bold" fill="#7b2d8e">${label}</text>` +
        `<text x="22" y="27" text-anchor="middle" font-size="7" fill="#999">거래</text>` +
        `</svg>`
    );
}

// ──────── 지도 초기화 ────────

function _parseHashParams() {
    const hash = window.location.hash.slice(1);
    const params = {};
    hash.split('&').forEach(p => { const [k, v] = p.split('='); if (k) params[k] = v; });
    return params;
}

function initMap() {
    const container = document.getElementById('mapContainer');
    if (!container) return;

    const hp = _parseHashParams();
    const initLat = parseFloat(hp.lat) || 37.5665;
    const initLng = parseFloat(hp.lng) || 126.9780;
    const hasFocus = hp.lat && hp.lng;

    map = new kakao.maps.Map(container, {
        center: new kakao.maps.LatLng(initLat, initLng),
        level: hasFocus ? 4 : 8,
    });
    clusterer = new kakao.maps.MarkerClusterer({ map, averageCenter: true, minLevel: 5 });
    infowindow = new kakao.maps.InfoWindow({ zIndex: 1 });

    loadMarkers();
}

// ──────── 마커 로드 ────────

async function loadMarkers(filters) {
    const hp = _parseHashParams();
    const focusId = hp.id ? parseInt(hp.id) : null;

    try {
        const resp = await fetch(MAP_API);
        if (!resp.ok) return;
        const data = await resp.json();

        clearMarkers();

        let filtered = data.markers || [];

        // 필터 적용
        if (filters) {
            if (filters.category === '건물') filtered = filtered.filter(m => m.property_type !== '토지');
            else if (filters.category === '토지') filtered = filtered.filter(m => m.property_type === '토지');
            if (filters.type) filtered = filtered.filter(m => m.property_type === filters.type);
            if (filters.priceMin) filtered = filtered.filter(m => m.price_krw >= filters.priceMin * 1e8);
            if (filters.priceMax) filtered = filtered.filter(m => m.price_krw <= filters.priceMax * 1e8);
            if (filters.scoreMin) filtered = filtered.filter(m => (m.score_composite || 0) >= filters.scoreMin);
            if (filters.candidateOnly) filtered = filtered.filter(m => m.is_candidate);
        }

        const kakaoMarkers = [];
        const focusMarkerMap = {};

        for (const m of filtered) {
            if (!m.lat || !m.lng) continue;

            const position = new kakao.maps.LatLng(m.lat, m.lng);
            const isLand = m.property_type === '토지';
            const isCandidate = m.is_candidate;
            const isTx = m.marker_type === 'transaction_summary';

            let markerSvg, imgSize, imgOffset;
            if (isTx) {
                markerSvg = makeTxSummaryMarkerSVG(m.tx_count || 0);
                imgSize = new kakao.maps.Size(44, 52);
                imgOffset = { offset: new kakao.maps.Point(22, 52) };
            } else {
                markerSvg = makeScoreMarkerSVG(m.score_composite, isCandidate, isLand);
                imgSize = new kakao.maps.Size(32, 44);
                imgOffset = { offset: new kakao.maps.Point(16, 44) };
            }

            const marker = new kakao.maps.Marker({
                position,
                image: new kakao.maps.MarkerImage(markerSvg, imgSize, imgOffset),
                zIndex: isCandidate ? 10 : isTx ? 5 : 1,
            });

            // 클릭 이벤트
            kakao.maps.event.addListener(marker, 'click', (function(m, marker) {
                return function() {
                    const score = m.score_composite ? m.score_composite.toFixed(0) : '-';
                    let content = '';
                    if (m.marker_type === 'transaction_summary') {
                        content = `<div style="padding:10px;min-width:220px;font-size:13px">
                            <strong style="color:#7b2d8e">📊 ${esc(m.label)}</strong><br>
                            <span style="color:#0d6efd;font-weight:700">평균 ${formatPrice(m.price_krw)}</span><br>
                            <small>평균 면적: ${m.area_m2 ? m.area_m2 + '㎡' : '-'} · 실거래 ${m.tx_count}건</small><br>
                            <a href="/search" style="font-size:12px;font-weight:600">이 지역 검색 →</a></div>`;
                    } else {
                        const candidateBadge = m.is_candidate ? '<span style="color:#e07a5f;margin-left:4px">★ 후보</span>' : '';
                        const typeLabel = m.property_type === '토지' ? '<strong style="color:#198754">[토지]</strong> ' : '<strong>';
                        const detailLink = m.id ? `<a href="/property/${m.id}" style="font-size:12px;font-weight:600">상세보기 →</a>` : '';
                        content = `<div style="padding:10px;min-width:200px;font-size:13px">
                            ${typeLabel}${esc(m.label)}</strong>${candidateBadge}<br>
                            <span style="color:#0d6efd;font-weight:700">${formatPrice(m.price_krw)}</span>
                            <span style="margin-left:6px">점수: ${score}</span><br>
                            <small>${m.property_type || ''} ${m.area_m2 ? m.area_m2 + '㎡' : ''}</small><br>
                            ${detailLink}</div>`;
                    }
                    infowindow.setContent(content);
                    infowindow.open(map, marker);
                };
            })(m, marker));

            markers.push(marker);
            kakaoMarkers.push(marker);
            if (m.id) focusMarkerMap[m.id] = marker;
        }

        clusterer.addMarkers(kakaoMarkers);

        // 사이드바 렌더링
        _lastFilteredData = filtered;
        renderSidebar();

        // 포커스 매물 인포윈도우 오픈
        if (focusId && focusMarkerMap[focusId]) {
            kakao.maps.event.trigger(focusMarkerMap[focusId], 'click');
        }

    } catch (e) {
        console.error('Map markers load error:', e);
        const pl = document.getElementById('propertyList');
        if (pl) pl.innerHTML = '<p class="text-muted text-center mt-3">매물 데이터를 불러올 수 없습니다</p>';
    }
}

// ──────── 사이드바 리스트 렌더링 (정렬 지원) ────────

function renderSidebar() {
    const propertyList = document.getElementById('propertyList');
    if (!propertyList) return;

    const sortField = document.getElementById('sortField')?.value || 'score_composite';
    const sorted = [..._lastFilteredData].sort((a, b) => {
        const va = a[sortField] || 0;
        const vb = b[sortField] || 0;
        return _mapSortAsc ? va - vb : vb - va;
    });

    if (sorted.length === 0) {
        propertyList.innerHTML = '<p class="text-muted text-center mt-3">매물이 없습니다</p>';
        return;
    }

    propertyList.innerHTML = `<p class="text-muted small mb-1">총 ${sorted.length}건</p>`;

    for (const m of sorted) {
        if (!m.lat || !m.lng) continue;
        const score = (m.score_composite || 0).toFixed(0);
        const scoreClass = score >= 80 ? 'score-high' : score >= 60 ? 'score-mid' : score >= 40 ? 'score-low' : 'score-vlow';
        const isTx = m.marker_type === 'transaction_summary';

        if (isTx) {
            propertyList.innerHTML += `
                <div class="property-list-item" onclick="panTo(${m.lat},${m.lng})" style="cursor:pointer">
                    <div class="d-flex justify-content-between">
                        <span class="name"><span class="badge bg-purple" style="font-size:0.65rem;background:#7b2d8e">실거래</span> ${esc(m.label)}</span>
                    </div>
                    <div class="price">평균 ${formatPrice(m.price_krw)}</div>
                </div>`;
        } else {
            const typeBadge = m.property_type === '토지'
                ? '<span class="badge bg-success" style="font-size:0.65rem;">토지</span>'
                : `<span class="badge bg-secondary" style="font-size:0.65rem;">${m.property_type || ''}</span>`;
            const detailBtn = m.id
                ? `<a href="/property/${m.id}" class="btn btn-outline-primary btn-sm py-0 px-1" style="font-size:0.7rem;" onclick="event.stopPropagation()"><i class="bi bi-eye"></i></a>`
                : '';
            propertyList.innerHTML += `
                <div class="property-list-item" onclick="panTo(${m.lat},${m.lng})" style="cursor:pointer">
                    <div class="d-flex justify-content-between">
                        <span class="name">${typeBadge} ${esc(m.label)}</span>
                        <span class="score-badge ${scoreClass}">${score}</span>
                    </div>
                    <div class="price">${formatPrice(m.price_krw)}</div>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="info">${m.is_candidate ? '★ 후보' : ''}</span>
                        ${detailBtn}
                    </div>
                </div>`;
        }
    }
}

function toggleMapSort() {
    _mapSortAsc = !_mapSortAsc;
    const btn = document.getElementById('sortDirBtn');
    if (btn) btn.textContent = _mapSortAsc ? '↑' : '↓';
    renderSidebar();
}

// 정렬 필드 변경 시 재렌더링
document.addEventListener('DOMContentLoaded', function() {
    const sortSelect = document.getElementById('sortField');
    if (sortSelect) sortSelect.addEventListener('change', renderSidebar);
});

function clearMarkers() {
    markers.forEach(m => kakao.maps.event.removeListener(m, 'click'));
    if (clusterer) clusterer.clear();
    markers = [];
}

function panTo(lat, lng) {
    if (map) {
        map.panTo(new kakao.maps.LatLng(lat, lng));
        map.setLevel(4);
    }
}

// ──────── 필터 적용 ────────

function applyFilters() {
    const filters = {
        category: document.getElementById('filterCategory')?.value || '',
        district: document.getElementById('filterDistrict')?.value || '',
        type: document.getElementById('filterType')?.value || '',
        priceMin: parseFloat(document.getElementById('filterPriceMin')?.value) || null,
        priceMax: parseFloat(document.getElementById('filterPriceMax')?.value) || null,
        scoreMin: parseFloat(document.getElementById('filterScoreMin')?.value) || 0,
        candidateOnly: document.getElementById('filterCandidateOnly')?.checked || false,
    };
    loadMarkers(filters);
}

// 점수 슬라이더 라벨
const scoreSlider = document.getElementById('filterScoreMin');
if (scoreSlider) {
    scoreSlider.addEventListener('input', function () {
        const label = document.getElementById('scoreMinLabel');
        if (label) label.textContent = `${this.value}점 이상`;
    });
}

// ──────── 카카오맵 로드 후 초기화 ────────

if (typeof kakao !== 'undefined' && kakao.maps) {
    kakao.maps.load(initMap);
} else {
    const container = document.getElementById('mapContainer');
    if (container) {
        container.innerHTML = `
            <div class="d-flex align-items-center justify-content-center h-100 bg-light">
                <div class="text-center text-muted">
                    <i class="bi bi-geo-alt" style="font-size:3rem"></i>
                    <p class="mt-2">카카오맵 API 키를 .env에 설정해주세요</p>
                    <small>KAKAO_REST_API_KEY=your_api_key</small>
                </div>
            </div>`;
    }
}
