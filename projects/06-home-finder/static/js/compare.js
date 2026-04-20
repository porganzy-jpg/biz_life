/**
 * HomeFinder - Property Comparison Module
 * 매물 비교 기능 (최대 3개까지 side-by-side 비교)
 */

const COMPARE_KEY = 'homefinder_compare_list';
let _compareRadarChart = null;

// ──────── sessionStorage helpers ────────

function _getCompareList() {
    try {
        const raw = sessionStorage.getItem(COMPARE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

function _setCompareList(list) {
    sessionStorage.setItem(COMPARE_KEY, JSON.stringify(list));
    _updateCompareCartBadge();
}

// ──────── Public API ────────

/**
 * 비교 목록에 매물 추가 (최대 3개)
 */
function addToCompare(propertyId) {
    const list = _getCompareList();
    const pid = Number(propertyId);
    if (list.includes(pid)) {
        _showCompareToast('이미 비교함에 추가된 매물입니다.');
        return;
    }
    if (list.length >= 3) {
        _showCompareToast('비교함은 최대 3개까지 가능합니다. 기존 항목을 먼저 제거하세요.');
        return;
    }
    list.push(pid);
    _setCompareList(list);
    _showCompareToast('비교함에 추가되었습니다. (' + list.length + '/3)');
}

/**
 * 비교 목록에서 매물 제거
 */
function removeFromCompare(propertyId) {
    const pid = Number(propertyId);
    let list = _getCompareList();
    list = list.filter(id => id !== pid);
    _setCompareList(list);
}

/**
 * 비교 모달 표시
 */
async function showCompareModal() {
    const list = _getCompareList();
    if (list.length < 2) {
        _showCompareToast('비교하려면 최소 2개의 매물이 필요합니다.');
        return;
    }

    const modalEl = document.getElementById('compareModal');
    if (!modalEl) return;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const body = document.getElementById('compare-modal-body');
    body.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div><p class="mt-2">매물 데이터를 불러오는 중...</p></div>';
    modal.show();

    try {
        // Fetch all properties in parallel
        const fetches = list.map(id => fetch(`/api/v1/properties/${id}`).then(r => {
            if (!r.ok) throw new Error(`매물 #${id} 로드 실패`);
            return r.json();
        }));
        const properties = await Promise.all(fetches);
        _renderCompareContent(properties, body);
    } catch (e) {
        body.innerHTML = `<div class="text-center py-5 text-danger"><i class="bi bi-exclamation-triangle" style="font-size:2rem;"></i><p class="mt-2">${e.message}</p></div>`;
    }
}

// ──────── Render compare modal content ────────

function _renderCompareContent(properties, container) {
    const count = properties.length;
    const colClass = count === 2 ? 'col-6' : 'col-4';

    // Find winners for each category
    const categories = [
        { key: 'score_composite', label: '종합점수', higher: true },
        { key: 'score_location', label: '위치', higher: true },
        { key: 'score_price', label: '가격', higher: true },
        { key: 'score_property', label: '매물', higher: true },
        { key: 'score_area', label: '지역', higher: true },
        { key: 'price_krw', label: '가격', higher: false },
        { key: 'area_m2', label: '면적', higher: true },
    ];

    function getWinner(key, higherIsBetter) {
        let best = null;
        let bestVal = higherIsBetter ? -Infinity : Infinity;
        for (const p of properties) {
            const val = p[key];
            if (val == null) continue;
            if (higherIsBetter ? val > bestVal : val < bestVal) {
                bestVal = val;
                best = p.id;
            }
        }
        return best;
    }

    const winners = {};
    for (const cat of categories) {
        winners[cat.key] = getWinner(cat.key, cat.higher);
    }

    // Build header cards
    let html = '<div class="row g-3 mb-4">';
    for (const p of properties) {
        const score = p.score_composite || 0;
        const scoreClass = score >= 70 ? 'bg-success' : score >= 45 ? 'bg-primary' : 'bg-secondary';
        const isScoreWinner = winners['score_composite'] === p.id;
        html += `
        <div class="${colClass}">
            <div class="card h-100 ${isScoreWinner ? 'border-success border-2' : ''}">
                <div class="card-body text-center">
                    <button class="btn btn-sm btn-outline-danger position-absolute top-0 end-0 m-2"
                            onclick="removeFromCompare(${p.id}); showCompareModal();" title="비교함에서 제거">
                        <i class="bi bi-x-lg"></i>
                    </button>
                    <div class="fw-bold mb-1">${p.complex_name || p.address || '매물 #' + p.id}</div>
                    <div class="text-muted small mb-2">${[p.district, p.dong].filter(Boolean).join(' ')}</div>
                    <div class="d-inline-flex align-items-center justify-content-center rounded-circle text-white ${scoreClass}" style="width:56px;height:56px;font-size:1.3rem;font-weight:bold;">
                        ${score.toFixed(0)}
                    </div>
                    <div class="small text-muted mt-1">종합점수</div>
                    <div class="fs-5 fw-bold text-primary mt-2">${_compareFormatPrice(p.price_krw)}</div>
                    <div class="small text-muted">${p.area_m2 ? p.area_m2 + 'm2' : '-'}</div>
                </div>
            </div>
        </div>`;
    }
    html += '</div>';

    // Score comparison bars
    html += '<div class="card mb-4"><div class="card-header fw-bold"><i class="bi bi-bar-chart"></i> 점수 비교</div><div class="card-body">';
    const scoreKeys = [
        { key: 'score_location', label: '위치 점수', icon: 'bi-geo-alt' },
        { key: 'score_price', label: '가격 점수', icon: 'bi-cash-coin' },
        { key: 'score_property', label: '매물 점수', icon: 'bi-house' },
        { key: 'score_area', label: '지역 점수', icon: 'bi-map' },
    ];
    const barColors = ['#0d6efd', '#198754', '#fd7e14'];

    for (const sk of scoreKeys) {
        html += `<div class="mb-3"><div class="fw-bold small mb-1"><i class="bi ${sk.icon} me-1"></i>${sk.label}</div>`;
        for (let i = 0; i < properties.length; i++) {
            const p = properties[i];
            const val = p[sk.key] || 0;
            const isWinner = winners[sk.key] === p.id;
            const name = p.complex_name || p.address || '매물 #' + p.id;
            html += `
            <div class="d-flex align-items-center mb-1">
                <div style="min-width:90px;font-size:0.8rem;" class="text-truncate">${name}</div>
                <div class="flex-grow-1 mx-2">
                    <div style="height:20px;background:#e9ecef;border-radius:4px;overflow:hidden;">
                        <div style="width:${val}%;height:100%;background:${barColors[i]};border-radius:4px;transition:width 0.5s;${isWinner ? 'box-shadow:0 0 0 2px #198754;' : ''}" class="d-flex align-items-center justify-content-end pe-1">
                            ${val >= 15 ? '<span style="font-size:0.7rem;color:white;font-weight:bold;">' + val.toFixed(0) + '</span>' : ''}
                        </div>
                    </div>
                </div>
                <div style="min-width:32px;font-size:0.8rem;font-weight:bold;${isWinner ? 'color:#198754;' : ''}">${val.toFixed(0)}${isWinner ? ' <i class="bi bi-trophy-fill" style="font-size:0.7rem;"></i>' : ''}</div>
            </div>`;
        }
        html += '</div>';
    }
    html += '</div></div>';

    // Radar chart overlay
    html += '<div class="card mb-4"><div class="card-header fw-bold"><i class="bi bi-pentagon"></i> 레이더 차트 비교</div><div class="card-body"><div class="d-flex justify-content-center"><canvas id="compare-radar-chart" height="260" style="max-width:400px;"></canvas></div></div></div>';

    // Detail comparison table
    html += '<div class="card mb-4"><div class="card-header fw-bold"><i class="bi bi-table"></i> 상세 비교</div><div class="card-body p-0">';
    html += '<table class="table table-bordered table-sm mb-0"><thead><tr><th style="min-width:100px;">항목</th>';
    for (const p of properties) {
        html += `<th class="text-center">${p.complex_name || p.address || '매물 #' + p.id}</th>`;
    }
    html += '</tr></thead><tbody>';

    const detailRows = [
        { label: '주소', render: p => [p.city, p.district, p.dong].filter(Boolean).join(' ') || '-' },
        { label: '유형', render: p => {
            let txt = p.property_type || '-';
            if (p.transaction_type && p.transaction_type !== '매매') txt += ' (' + p.transaction_type + ')';
            return txt;
        }},
        { label: '가격', render: p => {
            let txt = _compareFormatPrice(p.price_krw);
            if (p.transaction_type === '월세' && p.monthly_rent_krw) txt += ' / ' + Math.round(p.monthly_rent_krw/10000) + '만';
            return txt;
        }, winKey: 'price_krw' },
        { label: '면적', render: p => p.area_m2 ? formatArea(p.area_m2) : '-', winKey: 'area_m2' },
        { label: '평당가', render: p => {
            if (!p.price_krw || !p.area_m2) return '-';
            var pyeong = p.area_m2 / 3.3058;
            var ppp = Math.round(p.price_krw / pyeong);
            return formatPrice(ppp) + '/평';
        }, winKey: '_price_per_pyeong', customWin: true },
        { label: '전용면적', render: p => p.area_supply_m2 ? formatArea(p.area_supply_m2) : '-' },
        { label: '단지명', render: p => p.complex_name || '-' },
        { label: '층수', render: p => p.floor ? p.floor + '층' + (p.total_floors ? '/' + p.total_floors + '층' : '') : '-' },
        { label: '방향', render: p => p.direction || '-' },
        { label: '건축년도', render: p => p.built_year ? p.built_year + '년' : '-' },
        { label: '방/욕실', render: p => (p.rooms || '-') + '방 / ' + (p.bathrooms || '-') + '욕실' },
        { label: '관리비', render: p => p.maintenance_fee ? p.maintenance_fee + '만원' : '-' },
        { label: '지하철', render: p => p.nearest_subway_name ? p.nearest_subway_name + (p.nearest_subway_distance ? ' ' + Math.round(p.nearest_subway_distance) + 'm' : '') : '-' },
        { label: '공원', render: p => p.nearest_park_name ? p.nearest_park_name + (p.nearest_park_distance ? ' ' + Math.round(p.nearest_park_distance) + 'm' : '') : '-' },
        { label: '한강거리', render: p => p.nearest_river_distance ? Math.round(p.nearest_river_distance) + 'm' : '-' },
        { label: '출처', render: p => p.source || '-' },
    ];

    // Custom winner calculation for price per pyeong (lower is better)
    var pppWinner = null;
    var bestPPP = Infinity;
    for (const p of properties) {
        if (p.price_krw && p.area_m2) {
            var ppp = p.price_krw / (p.area_m2 / 3.3058);
            if (ppp < bestPPP) { bestPPP = ppp; pppWinner = p.id; }
        }
    }
    winners['_price_per_pyeong'] = pppWinner;

    for (const row of detailRows) {
        html += `<tr><td class="fw-bold small">${row.label}</td>`;
        for (const p of properties) {
            const isWinner = row.winKey && winners[row.winKey] === p.id;
            html += `<td class="text-center small ${isWinner ? 'table-success fw-bold' : ''}">${row.render(p)}</td>`;
        }
        html += '</tr>';
    }

    html += '</tbody></table></div></div>';

    // Action buttons per property
    html += '<div class="row g-3">';
    for (const p of properties) {
        html += `
        <div class="${colClass}">
            <div class="d-grid gap-2">
                <button class="btn btn-success btn-sm" onclick="pdmAddCandidateById(${p.id})">
                    <i class="bi bi-plus-circle"></i> 후보 추가
                </button>
                <button class="btn btn-primary btn-sm" onclick="showPropertyModal(${p.id}); bootstrap.Modal.getInstance(document.getElementById('compareModal')).hide();">
                    <i class="bi bi-eye"></i> 상세보기
                </button>
            </div>
        </div>`;
    }
    html += '</div>';

    container.innerHTML = html;

    // Render radar chart overlay after DOM is updated
    setTimeout(() => _renderCompareRadar(properties, barColors), 100);
}

// ──────── Radar chart with overlapping datasets ────────

function _renderCompareRadar(properties, colors) {
    const canvas = document.getElementById('compare-radar-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    if (_compareRadarChart) _compareRadarChart.destroy();

    const labels = ['위치', '가격', '매물', '지역'];
    const datasets = properties.map((p, i) => ({
        label: p.complex_name || p.address || '매물 #' + p.id,
        data: [p.score_location || 0, p.score_price || 0, p.score_property || 0, p.score_area || 0],
        borderColor: colors[i],
        backgroundColor: colors[i] + '22',
        pointBackgroundColor: colors[i],
        borderWidth: 2,
    }));

    _compareRadarChart = new Chart(canvas, {
        type: 'radar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    min: 0, max: 100,
                    ticks: { stepSize: 25, font: { size: 9 } },
                    pointLabels: { font: { size: 12 } },
                },
            },
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 11 } } },
            },
        },
    });
}

// ──────── Floating compare cart badge ────────

function _updateCompareCartBadge() {
    const list = _getCompareList();
    const btn = document.getElementById('compareCartBtn');
    const badge = document.getElementById('compareCartBadge');
    if (!btn || !badge) return;

    if (list.length > 0) {
        btn.style.display = 'flex';
        badge.textContent = list.length;
    } else {
        btn.style.display = 'none';
    }
}

// ──────── Toast notification ────────

function _showCompareToast(message) {
    // Use existing toast or create a temporary one
    let toastEl = document.getElementById('compareToast');
    if (toastEl) {
        toastEl.querySelector('.toast-body').textContent = message;
        const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2000 });
        toast.show();
    } else {
        // Fallback: brief alert-style notification
        const div = document.createElement('div');
        div.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-5 px-4 py-2 bg-dark text-white rounded-pill shadow';
        div.style.zIndex = '9999';
        div.style.fontSize = '0.9rem';
        div.textContent = message;
        document.body.appendChild(div);
        setTimeout(() => div.remove(), 2000);
    }
}

// ──────── Helper: format price ────────

function _compareFormatPrice(krw) {
    if (!krw) return '가격미정';
    const eok = Math.floor(krw / 100000000);
    const man = Math.floor((krw % 100000000) / 10000);
    if (eok > 0 && man > 0) return eok + '억 ' + man.toLocaleString() + '만';
    if (eok > 0) return eok + '억';
    return man.toLocaleString() + '만';
}

// ──────── Helper: add candidate directly by property ID ────────

async function pdmAddCandidateById(propertyId) {
    try {
        const resp = await fetch('/api/v1/candidates/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ property_id: parseInt(propertyId), priority: 3 })
        });
        if (resp.ok) {
            _showCompareToast('후보로 추가되었습니다!');
        } else {
            const err = await resp.json();
            _showCompareToast(err.detail || '추가 실패');
        }
    } catch (e) {
        _showCompareToast('오류: ' + e.message);
    }
}

// ──────── Init: update badge on page load ────────

document.addEventListener('DOMContentLoaded', function () {
    _updateCompareCartBadge();
});
