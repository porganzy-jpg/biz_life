/**
 * HomeFinder - 카카오맵 매물 지도
 */

const MAP_API = '/api/v1/dashboard/map-markers';
let map = null;
let markers = [];
let clusterer = null;
let infowindow = null;

// Land marker SVG (green pin with "T")
const LAND_MARKER_SVG = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="40" viewBox="0 0 28 40">' +
    '<path d="M14 0C6.3 0 0 6.3 0 14c0 10.5 14 26 14 26s14-15.5 14-26C28 6.3 21.7 0 14 0z" fill="#198754"/>' +
    '<circle cx="14" cy="14" r="8" fill="white"/>' +
    '<text x="14" y="18" text-anchor="middle" font-size="12" font-weight="bold" fill="#198754">T</text>' +
    '</svg>'
);

// ──────── 지도 초기화 ────────

function initMap() {
    const container = document.getElementById('mapContainer');
    if (!container) return;

    const options = {
        center: new kakao.maps.LatLng(37.5665, 126.9780), // 서울시청
        level: 8,
    };

    map = new kakao.maps.Map(container, options);
    clusterer = new kakao.maps.MarkerClusterer({
        map: map,
        averageCenter: true,
        minLevel: 5,
    });
    infowindow = new kakao.maps.InfoWindow({ zIndex: 1 });

    loadMarkers();
}

// ──────── 마커 로드 ────────

async function loadMarkers(filters) {
    try {
        const resp = await fetch(MAP_API);
        if (!resp.ok) return;
        const data = await resp.json();

        clearMarkers();

        const propertyList = document.getElementById('propertyList');
        if (propertyList) propertyList.innerHTML = '';

        let filtered = data.markers || [];

        // 필터 적용
        if (filters) {
            if (filters.category === '건물') {
                filtered = filtered.filter(m => m.property_type !== '토지');
            } else if (filters.category === '토지') {
                filtered = filtered.filter(m => m.property_type === '토지');
            }
            if (filters.type) {
                filtered = filtered.filter(m => m.property_type === filters.type);
            }
            if (filters.priceMin) {
                filtered = filtered.filter(m => m.price_krw >= filters.priceMin * 100000000);
            }
            if (filters.priceMax) {
                filtered = filtered.filter(m => m.price_krw <= filters.priceMax * 100000000);
            }
            if (filters.scoreMin) {
                filtered = filtered.filter(m => (m.score_composite || 0) >= filters.scoreMin);
            }
        }

        const kakaoMarkers = [];

        for (const m of filtered) {
            if (!m.lat || !m.lng) continue;

            const position = new kakao.maps.LatLng(m.lat, m.lng);

            // 토지는 커스텀 마커(초록), 건물은 기본 마커(빨간)
            const isLand = m.property_type === '토지';
            let markerOpts = { position: position };
            if (isLand && typeof kakao !== 'undefined') {
                const imgSize = new kakao.maps.Size(28, 40);
                const imgOption = { offset: new kakao.maps.Point(14, 40) };
                markerOpts.image = new kakao.maps.MarkerImage(LAND_MARKER_SVG, imgSize, imgOption);
            }
            const marker = new kakao.maps.Marker(markerOpts);

            // 클릭 이벤트 (토지/건물 분기)
            kakao.maps.event.addListener(marker, 'click', function () {
                const score = m.score_composite ? m.score_composite.toFixed(0) : '-';
                let content = '';
                if (isLand) {
                    content = `
                    <div style="padding:10px;min-width:200px;font-size:13px">
                        <strong style="color:#198754">[토지]</strong> ${m.label}
                        ${m.is_candidate ? '<span style="color:#198754;margin-left:4px">★ 후보</span>' : ''}
                        <br>
                        <span style="color:#0d6efd;font-weight:700">${formatPrice(m.price_krw)}</span>
                        <span style="margin-left:6px">점수: ${score}</span>
                        <br>
                        <small>${m.area_m2 ? m.area_m2 + '㎡' : ''} · ${m.land_use || ''} · ${m.zoning_type || ''}</small>
                        <br>
                        <small>건폐${m.building_coverage_ratio || '-'}% / 용적${m.floor_area_ratio || '-'}%</small>
                        <br>
                        <a href="/property/${m.id}" style="font-size:12px">상세보기 →</a>
                    </div>`;
                } else {
                    content = `
                    <div style="padding:10px;min-width:200px;font-size:13px">
                        <strong>${m.label}</strong>
                        ${m.is_candidate ? '<span style="color:#198754;margin-left:4px">★ 후보</span>' : ''}
                        <br>
                        <span style="color:#0d6efd;font-weight:700">${formatPrice(m.price_krw)}</span>
                        <span style="margin-left:6px">점수: ${score}</span>
                        <br>
                        <small>${m.property_type || ''} ${m.acquisition_type || ''}</small>
                        <br>
                        <a href="/property/${m.id}" style="font-size:12px">상세보기 →</a>
                    </div>`;
                }
                infowindow.setContent(content);
                infowindow.open(map, marker);
            });

            markers.push(marker);
            kakaoMarkers.push(marker);

            // 사이드바 리스트
            if (propertyList) {
                const scoreClass = (m.score_composite || 0) >= 80 ? 'score-high' :
                                   (m.score_composite || 0) >= 60 ? 'score-mid' :
                                   (m.score_composite || 0) >= 40 ? 'score-low' : 'score-vlow';
                const typeBadge = isLand
                    ? '<span class="badge bg-success" style="font-size:0.65rem;">토지</span>'
                    : `<span class="badge bg-secondary" style="font-size:0.65rem;">${m.property_type || ''}</span>`;
                propertyList.innerHTML += `
                    <div class="property-list-item" onclick="panTo(${m.lat},${m.lng})">
                        <div class="d-flex justify-content-between">
                            <span class="name">${typeBadge} ${m.label}</span>
                            <span class="score-badge ${scoreClass}">${(m.score_composite || 0).toFixed(0)}</span>
                        </div>
                        <div class="price">${formatPrice(m.price_krw)}</div>
                        <div class="info">${m.property_type || ''} ${m.is_candidate ? '★ 후보' : ''}</div>
                    </div>`;
            }
        }

        clusterer.addMarkers(kakaoMarkers);

        if (propertyList && filtered.length === 0) {
            propertyList.innerHTML = '<p class="text-muted text-center mt-3">매물이 없습니다</p>';
        }

    } catch (e) {
        console.error('Map markers load error:', e);
        const propertyList = document.getElementById('propertyList');
        if (propertyList) {
            propertyList.innerHTML = '<p class="text-muted text-center mt-3">매물 데이터를 불러올 수 없습니다</p>';
        }
    }
}

function clearMarkers() {
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
    // kakao API가 로드되지 않은 경우 (API 키 누락)
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
