/**
 * HomeFinder - 대시보드 페이지 JS
 */

const API_BASE = '/api/v1';
let pipelineChart = null;
let priceChart = null;
let _allActivities = [];  // Store activities for filtering
let _currentActivityFilter = 'all';

// ──────── 대시보드 요약 로드 ────────

async function loadDashboardSummary() {
    try {
        const resp = await fetch(`${API_BASE}/dashboard/summary`);
        if (!resp.ok) return;
        const data = await resp.json();

        document.getElementById('totalProperties').textContent =
            (data.active_properties || 0).toLocaleString();
        // 건물/토지 카운트 서브텍스트
        const subEl = document.getElementById('propertySub');
        if (subEl && data.building_count != null && data.land_count != null) {
            subEl.textContent = `건물 ${data.building_count}건 / 토지 ${data.land_count}건`;
        }
        document.getElementById('totalCandidates').textContent =
            (data.pipeline?.total || 0).toLocaleString();
        document.getElementById('weeklyAuctions').textContent =
            (data.active_auctions || 0).toLocaleString();
        document.getElementById('activeSubscriptions').textContent =
            (data.active_subscriptions || 0).toLocaleString();

        // Pipeline chart
        if (data.pipeline?.counts) {
            if (pipelineChart) pipelineChart.destroy();
            pipelineChart = renderPipelineChart('pipelineChart', data.pipeline.counts);
        }
    } catch (e) {
        console.error('Dashboard summary load error:', e);
    }
}

// ──────── 상위 매물 테이블 로드 ────────

async function loadTopProperties() {
    try {
        const resp = await fetch(`${API_BASE}/properties/top?limit=10`);
        if (!resp.ok) return;
        const data = await resp.json();
        const tbody = document.getElementById('topScoredTable');
        if (!tbody) return;

        if (!data.items || data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">등록된 매물이 없습니다</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        for (const p of data.items) {
            const score = p.score_composite || 0;
            const badgeClass = getScoreBadgeClass(score);
            tbody.innerHTML += `
                <tr onclick="showPropertyModal(${p.id})" style="cursor:pointer" title="클릭하여 상세보기">
                    <td class="fw-bold">${p.complex_name || p.address || '매물 ' + p.id}</td>
                    <td>${p.district || ''} ${p.dong || ''}</td>
                    <td class="text-primary fw-bold">${formatPrice(p.price_krw)}</td>
                    <td>${p.area_m2 ? p.area_m2 + '㎡' : '-'}</td>
                    <td><span class="badge ${badgeClass}">${score.toFixed(0)}</span></td>
                </tr>`;
        }
    } catch (e) {
        console.error('Top properties load error:', e);
    }
}

// ──────── 가격 추이 차트 ────────

async function loadPriceChart(district) {
    try {
        const resp = await fetch(`${API_BASE}/dashboard/summary`);
        if (!resp.ok) return;
        const data = await resp.json();

        // Placeholder: 가격 데이터가 쌓이면 실제 추이 표시
        // 현재는 price_stats 기반으로 간단한 표시
        const ctx = document.getElementById('priceChart');
        if (!ctx) return;

        if (priceChart) priceChart.destroy();

        const stats = data.price_stats;
        if (stats) {
            priceChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['최저', '평균', '최고'],
                    datasets: [{
                        label: district || '전체',
                        data: [stats.min_price_krw, stats.avg_price_krw, stats.max_price_krw],
                        backgroundColor: ['#198754', '#0d6efd', '#dc3545'],
                        borderRadius: 6,
                    }],
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { ticks: { callback: v => formatPrice(v) } },
                    },
                },
            });
        } else {
            priceChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['데이터 없음'],
                    datasets: [{ label: '-', data: [0], backgroundColor: '#ddd' }],
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                },
            });
        }
    } catch (e) {
        console.error('Price chart load error:', e);
    }
}

// ──────── 최근 활동 로드 ────────

async function loadRecentActivity() {
    try {
        const resp = await fetch(`${API_BASE}/dashboard/recent-activity?days=7&limit=15`);
        if (!resp.ok) return;
        const data = await resp.json();
        const container = document.getElementById('recentActivity');
        if (!container) return;

        if (!data.activities || data.activities.length === 0) {
            _allActivities = [];
            container.innerHTML = '<p class="text-muted text-center">최근 활동이 없습니다</p>';
            return;
        }

        _allActivities = data.activities;
        _renderFilteredActivities();
    } catch (e) {
        console.error('Recent activity load error:', e);
    }
}

// ──────── 활동 필터링 ────────

function _getActivityFilterCategory(type) {
    if (type === 'new_property' || type === 'property_updated') return 'property';
    if (type === 'new_candidate' || type === 'candidate_status') return 'candidate';
    if (type === 'price_change' || type === 'price_updated') return 'price';
    return 'other';
}

function _getActivityIcon(type) {
    switch (type) {
        case 'new_property':       return 'bi-house-add text-primary';
        case 'property_updated':   return 'bi-pencil-square text-info';
        case 'new_candidate':      return 'bi-star-fill text-success';
        case 'candidate_status':   return 'bi-arrow-right-circle text-success';
        case 'price_change':       return 'bi-graph-up-arrow text-warning';
        case 'price_updated':      return 'bi-currency-exchange text-warning';
        default:                   return 'bi-circle text-muted';
    }
}

function _getDateGroup(isoStr) {
    if (!isoStr) return '이전';
    const now = new Date();
    const date = new Date(isoStr);
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    // Check if same calendar day
    const isToday = now.toDateString() === date.toDateString();
    if (isToday) return '오늘';

    // Check if within this week (7 days)
    if (diffDays < 7) return '이번주';

    return '이전';
}

function filterActivities(filter) {
    _currentActivityFilter = filter;

    // Update button states
    const group = document.getElementById('activityFilterGroup');
    if (group) {
        group.querySelectorAll('button').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-filter') === filter);
        });
    }

    _renderFilteredActivities();
}

function _renderFilteredActivities() {
    const container = document.getElementById('recentActivity');
    if (!container) return;

    // Filter activities
    let filtered = _allActivities;
    if (_currentActivityFilter !== 'all') {
        filtered = _allActivities.filter(a => _getActivityFilterCategory(a.type) === _currentActivityFilter);
    }

    if (filtered.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">해당 활동이 없습니다</p>';
        return;
    }

    // Group by date
    const groups = { '오늘': [], '이번주': [], '이전': [] };
    for (const a of filtered) {
        const group = _getDateGroup(a.timestamp);
        groups[group].push(a);
    }

    let html = '';
    const groupOrder = ['오늘', '이번주', '이전'];
    const groupIcons = { '오늘': 'bi-calendar-check', '이번주': 'bi-calendar-week', '이전': 'bi-calendar' };

    for (const g of groupOrder) {
        if (groups[g].length === 0) continue;

        html += `<div class="mb-2"><div class="small fw-bold text-muted mb-1"><i class="bi ${groupIcons[g]} me-1"></i>${g} <span class="badge bg-light text-dark">${groups[g].length}</span></div>`;

        for (const a of groups[g]) {
            const icon = _getActivityIcon(a.type);
            html += `
                <div class="activity-item">
                    <i class="bi ${icon} activity-icon"></i>
                    <span>${a.description}</span>
                    ${a.price_krw ? '<span class="text-primary ms-1">' + formatPrice(a.price_krw) + '</span>' : ''}
                    <div class="activity-time">${timeAgo(a.timestamp)}</div>
                </div>`;
        }
        html += '</div>';
    }

    container.innerHTML = html;
}

// ──────── 가격 예측 테이블 로드 ────────

async function loadDistrictForecast() {
    const tbody = document.getElementById('forecastTable');
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">로딩중...</td></tr>';

    try {
        const resp = await fetch(`${API_BASE}/predictions/district-forecast`);
        if (!resp.ok) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">데이터를 불러올 수 없습니다</td></tr>';
            return;
        }
        const data = await resp.json();

        if (!data.forecasts || data.forecasts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">예측 데이터가 없습니다</td></tr>';
            return;
        }

        tbody.innerHTML = '';
        for (const f of data.forecasts) {
            const changePct = f.change_pct || 0;
            const isUp = f.trend_direction === 'up';
            const isDown = f.trend_direction === 'down';
            const trendColor = isUp ? 'text-danger' : (isDown ? 'text-primary' : 'text-muted');
            const trendIcon = isUp ? 'bi-arrow-up-circle-fill' : (isDown ? 'bi-arrow-down-circle-fill' : 'bi-dash-circle');
            const changeColor = changePct > 0 ? 'text-danger' : (changePct < 0 ? 'text-primary' : 'text-muted');

            // Confidence bar
            const confPct = Math.round((f.confidence || 0) * 100);
            const confColor = confPct >= 60 ? 'bg-success' : (confPct >= 30 ? 'bg-warning' : 'bg-secondary');

            tbody.innerHTML += `
                <tr>
                    <td class="fw-bold">${f.district || '-'}</td>
                    <td>${f.property_count || '-'}</td>
                    <td class="text-end">${formatPrice(f.current_avg)}</td>
                    <td class="text-end">${formatPrice(f.predicted_avg)}</td>
                    <td class="text-end ${changeColor} fw-bold">
                        ${changePct > 0 ? '+' : ''}${changePct.toFixed(1)}%
                    </td>
                    <td class="text-center">
                        <i class="bi ${trendIcon} ${trendColor}" style="font-size:1.2rem;" title="${f.trend_direction}"></i>
                    </td>
                    <td class="text-center">
                        <div class="progress" style="height:6px;min-width:50px;" title="${confPct}%">
                            <div class="progress-bar ${confColor}" style="width:${confPct}%"></div>
                        </div>
                        <small class="text-muted" style="font-size:0.7rem;">${confPct}%</small>
                    </td>
                </tr>`;
        }
    } catch (e) {
        console.error('District forecast load error:', e);
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-danger">로드 오류</td></tr>';
    }
}

// ──────── 기회 매물 카드 로드 ────────

async function loadOpportunities() {
    const container = document.getElementById('opportunityCards');
    if (!container) return;

    container.innerHTML = '<div class="col-12 text-center text-muted">로딩중...</div>';

    try {
        const resp = await fetch(`${API_BASE}/predictions/opportunities?limit=5`);
        if (!resp.ok) {
            container.innerHTML = '<div class="col-12 text-center text-muted">데이터를 불러올 수 없습니다</div>';
            return;
        }
        const data = await resp.json();

        if (!data.opportunities || data.opportunities.length === 0) {
            container.innerHTML = '<div class="col-12 text-center text-muted">기회 매물이 없습니다</div>';
            return;
        }

        container.innerHTML = '';
        for (const opp of data.opportunities) {
            const name = opp.complex_name || opp.address || '매물 #' + opp.id;
            const location = [opp.district, opp.dong].filter(Boolean).join(' ');
            const oppScore = opp.opportunity_score || 0;
            const discount = opp.discount_pct || 0;
            const composite = opp.score_composite || 0;

            // Opportunity badge color
            let badgeBg = 'bg-secondary';
            if (oppScore >= 70) badgeBg = 'bg-danger';
            else if (oppScore >= 50) badgeBg = 'bg-warning text-dark';
            else if (oppScore >= 30) badgeBg = 'bg-info text-dark';

            // Discount display
            const discountDisplay = discount > 0
                ? `<span class="text-success fw-bold">-${discount.toFixed(1)}%</span>`
                : (discount < 0 ? `<span class="text-danger">+${Math.abs(discount).toFixed(1)}%</span>` : '<span class="text-muted">-</span>');

            container.innerHTML += `
                <div class="col-md-4 col-lg mb-2">
                    <div class="card h-100 border-0 shadow-sm" style="cursor:pointer;transition:transform .15s,box-shadow .15s;"
                         onclick="showPropertyModal(${opp.id})"
                         onmouseover="this.style.transform='translateY(-3px)';this.style.boxShadow='0 4px 14px rgba(0,0,0,0.15)'"
                         onmouseout="this.style.transform='';this.style.boxShadow='0 .125rem .25rem rgba(0,0,0,.075)'">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <h6 class="card-title mb-0 text-truncate" style="max-width:160px;" title="${name}">${name}</h6>
                                    <small class="text-muted">${location}</small>
                                </div>
                                <span class="badge ${badgeBg} rounded-pill" style="font-size:0.85rem;" title="기회 점수">
                                    ${oppScore.toFixed(0)}
                                </span>
                            </div>
                            <div class="mb-1">
                                <span class="text-primary fw-bold">${formatPrice(opp.price_krw)}</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center" style="font-size:0.8rem;">
                                <span>할인 ${discountDisplay}</span>
                                <span class="text-muted" title="종합점수">
                                    <i class="bi bi-star-fill" style="font-size:0.7rem;"></i> ${composite.toFixed(0)}점
                                </span>
                            </div>
                        </div>
                    </div>
                </div>`;
        }
    } catch (e) {
        console.error('Opportunities load error:', e);
        container.innerHTML = '<div class="col-12 text-center text-danger">로드 오류</div>';
    }
}

// ──────── 마지막 업데이트 시간 표시 ────────

function updateLastUpdateTime() {
    const el = document.getElementById('lastUpdate');
    if (el) {
        const now = new Date();
        el.textContent = `${now.getHours()}:${String(now.getMinutes()).padStart(2, '0')} 업데이트`;
    }
}

// ──────── 가격 지역 선택 이벤트 ────────

const districtSelect = document.getElementById('priceDistrictSelect');
if (districtSelect) {
    districtSelect.addEventListener('change', function () {
        loadPriceChart(this.value);
    });
}

// ──────── 초기 로드 ────────

loadDashboardSummary();
loadTopProperties();
loadDistrictForecast();
loadOpportunities();
loadPriceChart('서울');
loadRecentActivity();
updateLastUpdateTime();
