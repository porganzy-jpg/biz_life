/**
 * HomeFinder - 대시보드 페이지 JS
 */

const API_BASE = '/api/v1';
let pipelineChart = null;
let priceChart = null;

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
            container.innerHTML = '<p class="text-muted text-center">최근 활동이 없습니다</p>';
            return;
        }

        container.innerHTML = '';
        for (const a of data.activities) {
            const icon = a.type === 'new_property' ? 'bi-house-add text-primary' :
                         a.type === 'property_updated' ? 'bi-pencil-square text-warning' :
                         a.type === 'new_candidate' ? 'bi-star text-success' :
                         'bi-circle text-muted';
            container.innerHTML += `
                <div class="activity-item">
                    <i class="bi ${icon} activity-icon"></i>
                    <span>${a.description}</span>
                    ${a.price_krw ? '<span class="text-primary ms-1">' + formatPrice(a.price_krw) + '</span>' : ''}
                    <div class="activity-time">${timeAgo(a.timestamp)}</div>
                </div>`;
        }
    } catch (e) {
        console.error('Recent activity load error:', e);
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
loadPriceChart('서울');
loadRecentActivity();
updateLastUpdateTime();
