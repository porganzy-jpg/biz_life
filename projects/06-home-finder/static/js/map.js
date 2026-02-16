/**
 * HomeFinder - 카카오맵 매물 지도
 */

const MAP_API = '/api/v1/dashboard/map-markers';
let map = null;
let markers = [];
let clusterer = null;
let infowindow = null;

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
            if (filters.district) {
                // Note: markers don't have district, we'd need to filter via API
                // For now, skip client-side district filtering
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

            // 마커 색상 (점수 기반)
            const marker = new kakao.maps.Marker({ position: position });

            // 클릭 이벤트
            kakao.maps.event.addListener(marker, 'click', function () {
                const score = m.score_composite ? m.score_composite.toFixed(0) : '-';
                const content = `
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
                propertyList.innerHTML += `
                    <div class="property-list-item" onclick="panTo(${m.lat},${m.lng})">
                        <div class="d-flex justify-content-between">
                            <span class="name">${m.label}</span>
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
