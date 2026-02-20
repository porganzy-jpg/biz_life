/**
 * HomeFinder - Property Detail Modal
 * 매물 클릭 시 모달로 상세 정보를 보여주는 공유 컴포넌트
 */

let _propertyModalInstance = null;
let _modalRadarChart = null;

function _getPropertyModal() {
    if (!_propertyModalInstance) {
        const el = document.getElementById('propertyDetailModal');
        if (el) _propertyModalInstance = new bootstrap.Modal(el);
    }
    return _propertyModalInstance;
}

/**
 * 매물 상세 모달 표시
 * @param {number} propertyId - 매물 ID
 */
async function showPropertyModal(propertyId) {
    const modal = _getPropertyModal();
    if (!modal) return;

    // 로딩 상태
    document.getElementById('pdm-loading').style.display = 'flex';
    document.getElementById('pdm-content').style.display = 'none';
    document.getElementById('pdm-error').style.display = 'none';
    modal.show();

    try {
        const resp = await fetch(`/api/v1/properties/${propertyId}`);
        if (!resp.ok) throw new Error('매물을 찾을 수 없습니다');
        const p = await resp.json();
        _renderPropertyModal(p);
    } catch (e) {
        document.getElementById('pdm-loading').style.display = 'none';
        document.getElementById('pdm-error').style.display = 'block';
        document.getElementById('pdm-error-msg').textContent = e.message;
    }
}

function _renderPropertyModal(p) {
    const isLand = p.property_type === '토지';

    // Header
    const title = p.complex_name || p.address || '매물 #' + p.id;
    document.getElementById('pdm-title').textContent = title;
    const typeBadge = document.getElementById('pdm-type-badge');
    typeBadge.textContent = p.property_type || '-';
    typeBadge.className = 'badge ' + (isLand ? 'bg-success' : 'bg-primary');

    const acqBadge = document.getElementById('pdm-acq-badge');
    if (p.acquisition_type) {
        acqBadge.textContent = p.acquisition_type;
        acqBadge.style.display = 'inline';
    } else {
        acqBadge.style.display = 'none';
    }

    // Price
    document.getElementById('pdm-price').textContent = _modalFormatPrice(p.price_krw);
    document.getElementById('pdm-price-m2').textContent = p.price_per_m2
        ? Math.round(p.price_per_m2 / 10000).toLocaleString() + '만/m2'
        : '';

    // Location
    document.getElementById('pdm-location').textContent =
        [p.city, p.district, p.dong, p.address].filter(Boolean).join(' ');

    // Composite score
    const score = p.score_composite || 0;
    const scoreEl = document.getElementById('pdm-score');
    scoreEl.textContent = score.toFixed(0);
    scoreEl.className = 'pdm-score-circle ' + _modalScoreClass(score);

    // Sub-scores
    _setSubScore('pdm-sub-location', p.score_location);
    _setSubScore('pdm-sub-price', p.score_price);
    _setSubScore('pdm-sub-property', p.score_property);
    _setSubScore('pdm-sub-area', p.score_area);

    // Property label for score
    document.getElementById('pdm-prop-label').textContent = isLand ? '토지' : '매물';

    // Building info
    const buildingInfo = document.getElementById('pdm-building-info');
    const landInfo = document.getElementById('pdm-land-info');

    if (isLand) {
        buildingInfo.style.display = 'none';
        landInfo.style.display = 'block';
        document.getElementById('pdm-land-use').textContent = p.land_use || '-';
        document.getElementById('pdm-land-zoning').textContent = p.zoning_type || '-';
        document.getElementById('pdm-land-bcr').textContent = p.building_coverage_ratio != null ? p.building_coverage_ratio + '%' : '-';
        document.getElementById('pdm-land-far').textContent = p.floor_area_ratio != null ? p.floor_area_ratio + '%' : '-';
        document.getElementById('pdm-land-road').textContent = p.road_frontage || '-';
        document.getElementById('pdm-land-topo').textContent = p.topography || '-';
        document.getElementById('pdm-land-area').textContent = p.area_m2
            ? p.area_m2 + 'm2 (' + Math.round(p.area_m2 / 3.3058) + '평)'
            : '-';
    } else {
        buildingInfo.style.display = 'block';
        landInfo.style.display = 'none';
        document.getElementById('pdm-area').textContent = p.area_m2 ? p.area_m2 + 'm2' : '-';
        document.getElementById('pdm-supply-area').textContent = p.area_supply_m2 ? p.area_supply_m2 + 'm2' : '';
        document.getElementById('pdm-floor').textContent = p.floor
            ? p.floor + '층' + (p.total_floors ? '/' + p.total_floors + '층' : '')
            : '-';
        document.getElementById('pdm-direction').textContent = p.direction || '-';
        document.getElementById('pdm-built-year').textContent = p.built_year
            ? p.built_year + '년 (' + (new Date().getFullYear() - p.built_year) + '년차)'
            : '-';
        document.getElementById('pdm-rooms').textContent =
            (p.rooms || '-') + '방 / ' + (p.bathrooms || '-') + '욕실';
        document.getElementById('pdm-maintenance').textContent = p.maintenance_fee
            ? p.maintenance_fee + '만원'
            : '-';
        document.getElementById('pdm-complex').textContent = p.complex_name || '-';
    }

    // Infrastructure
    document.getElementById('pdm-subway').textContent = p.nearest_subway_name
        ? p.nearest_subway_name + (p.nearest_subway_distance ? ' ' + Math.round(p.nearest_subway_distance) + 'm' : '')
        : '-';
    document.getElementById('pdm-subway-lines').textContent = p.nearest_subway_lines || '';
    document.getElementById('pdm-park').textContent = p.nearest_park_name
        ? p.nearest_park_name + (p.nearest_park_distance ? ' ' + Math.round(p.nearest_park_distance) + 'm' : '')
        : '-';
    document.getElementById('pdm-river').textContent = p.nearest_river_distance
        ? Math.round(p.nearest_river_distance) + 'm'
        : '-';

    // Description
    const descEl = document.getElementById('pdm-description');
    if (p.description) {
        descEl.textContent = p.description;
        descEl.style.display = 'block';
    } else {
        descEl.style.display = 'none';
    }

    // Source info
    document.getElementById('pdm-source').textContent = p.source || '-';
    document.getElementById('pdm-created').textContent = p.created_at
        ? new Date(p.created_at).toLocaleDateString('ko-KR')
        : '-';

    // Action links
    document.getElementById('pdm-link-detail').href = '/property/' + p.id;
    const sourceLink = document.getElementById('pdm-link-source');
    if (p.source_url) {
        sourceLink.href = p.source_url;
        sourceLink.style.display = 'inline-block';
    } else {
        sourceLink.style.display = 'none';
    }

    // Store property ID for actions
    document.getElementById('pdm-property-id').value = p.id;

    // Radar chart
    const radarCanvas = document.getElementById('pdm-radar');
    if (radarCanvas && typeof Chart !== 'undefined') {
        if (_modalRadarChart) _modalRadarChart.destroy();
        const radarLabel = isLand ? '토지' : '매물';
        _modalRadarChart = new Chart(radarCanvas, {
            type: 'radar',
            data: {
                labels: ['위치', '가격', radarLabel, '지역'],
                datasets: [{
                    label: '점수',
                    data: [p.score_location || 0, p.score_price || 0, p.score_property || 0, p.score_area || 0],
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13,110,253,0.15)',
                    pointBackgroundColor: '#0d6efd',
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    r: { min: 0, max: 100, ticks: { stepSize: 25, font: { size: 9 } }, pointLabels: { font: { size: 11 } } },
                },
                plugins: { legend: { display: false } },
            },
        });
    }

    // Show content
    document.getElementById('pdm-loading').style.display = 'none';
    document.getElementById('pdm-content').style.display = 'block';
}

function _setSubScore(id, score) {
    const el = document.getElementById(id);
    if (!el) return;
    const s = score || 0;
    el.querySelector('.pdm-sub-fill').style.width = s + '%';
    el.querySelector('.pdm-sub-fill').style.background = _modalSubColor(s);
    el.querySelector('.pdm-sub-value').textContent = s.toFixed(0);
}

function _modalFormatPrice(krw) {
    if (!krw) return '가격미정';
    const eok = Math.floor(krw / 100000000);
    const man = Math.floor((krw % 100000000) / 10000);
    if (eok > 0 && man > 0) return eok + '억 ' + man.toLocaleString() + '만';
    if (eok > 0) return eok + '억';
    return man.toLocaleString() + '만';
}

function _modalScoreClass(s) {
    if (s >= 70) return 'pdm-score-high';
    if (s >= 45) return 'pdm-score-mid';
    return 'pdm-score-low';
}

function _modalSubColor(s) {
    if (s >= 70) return '#198754';
    if (s >= 45) return '#0d6efd';
    return '#6c757d';
}

async function pdmAddCandidate() {
    const propId = document.getElementById('pdm-property-id').value;
    try {
        const resp = await fetch('/api/v1/candidates/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ property_id: parseInt(propId), priority: 3 })
        });
        if (resp.ok) {
            const btn = document.getElementById('pdm-btn-candidate');
            btn.textContent = '추가 완료!';
            btn.classList.replace('btn-success', 'btn-secondary');
            btn.disabled = true;
            setTimeout(() => {
                btn.innerHTML = '<i class="bi bi-plus-circle"></i> 후보 추가';
                btn.classList.replace('btn-secondary', 'btn-success');
                btn.disabled = false;
            }, 2000);
        } else {
            const err = await resp.json();
            alert(err.detail || '추가 실패');
        }
    } catch (e) {
        alert('오류: ' + e.message);
    }
}

async function pdmRescore() {
    const propId = document.getElementById('pdm-property-id').value;
    const btn = document.getElementById('pdm-btn-rescore');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 채점중...';
    try {
        await fetch('/api/v1/properties/' + propId + '/score', { method: 'POST' });
        await showPropertyModal(parseInt(propId));
    } catch (e) {
        alert('채점 실패: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 재채점';
    }
}
