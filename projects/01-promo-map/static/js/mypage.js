/**
 * PromoMap 마이페이지 탭
 */

async function loadMypage() {
    const container = document.getElementById('mypageContent');

    if (!API.isLoggedIn()) {
        container.innerHTML = `
            <div class="login-prompt">
                <p>마이페이지를 보려면 로그인이 필요합니다</p>
                <button class="btn-primary" onclick="openAuthModal()">로그인</button>
            </div>
        `;
        return;
    }

    container.innerHTML = '<div class="loading-text">불러오는 중...</div>';

    try {
        const profile = await API.getProfile();
        const user = API.getUser();
        const initial = (profile.name || 'U').charAt(0).toUpperCase();

        container.innerHTML = `
            <div class="profile-card">
                <div class="profile-header">
                    <div class="profile-avatar">${initial}</div>
                    <div class="profile-info">
                        <h3>${profile.name}</h3>
                        <p>${profile.email}</p>
                        ${profile.company_name ? `<p>${profile.company_name}</p>` : ''}
                    </div>
                </div>
                <div class="profile-stats">
                    <div class="stat-item">
                        <div class="stat-value">${profile.favorites_count}</div>
                        <div class="stat-label">즐겨찾기</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${profile.reviews_count}</div>
                        <div class="stat-label">리뷰</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${profile.usage_count}</div>
                        <div class="stat-label">사용 횟수</div>
                    </div>
                </div>
            </div>

            <div id="redemptionStatsSection"></div>

            <div id="savingsAnalytics"></div>

            <div id="redemptionHistorySection"></div>

            <div class="menu-list">
                <div class="menu-item" onclick="showRedemptionHistory()">
                    <span>할인 코드 사용 내역</span><span>→</span>
                </div>
                <div class="menu-item" onclick="showUsageHistory()">
                    <span>사용 이력</span><span>→</span>
                </div>
                <div class="menu-item" onclick="showActiveDiscounts()">
                    <span>내 회사 할인</span><span>→</span>
                </div>
                <div class="menu-item" onclick="showEditProfile()">
                    <span>프로필 수정</span><span>→</span>
                </div>
                <div class="menu-item" onclick="handleLogout()" style="color:#FF3B30;">
                    <span>로그아웃</span><span></span>
                </div>
            </div>
        `;

        // 절약 분석 로드
        loadSavingsAnalytics();

        // 코드 기반 절약 통계 + 최근 내역 로드
        loadRedemptionStats();
        loadRedemptionHistoryPreview();
    } catch (e) {
        container.innerHTML = '<div class="empty-state">정보를 불러올 수 없습니다</div>';
    }
}

async function showUsageHistory() {
    const container = document.getElementById('mypageContent');
    container.innerHTML = '<div class="loading-text">불러오는 중...</div>';

    try {
        const data = await API.getUsageHistory();
        let html = `
            <div style="margin-bottom:12px;">
                <button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="loadMypage()">← 돌아가기</button>
                <h3 style="margin-top:12px;">사용 이력</h3>
            </div>
        `;

        if (!data.items || data.items.length === 0) {
            html += '<div class="empty-state">사용 이력이 없습니다</div>';
        } else {
            html += data.items.map(item => `
                <div class="history-item">
                    <div>
                        <div class="history-store">${item.store_name}</div>
                        <div class="history-desc">${item.discount_description}</div>
                        <div class="history-date">${item.used_at ? item.used_at.split('T')[0] : ''}</div>
                    </div>
                    <div class="history-amount">${item.discount_value}% OFF</div>
                </div>
            `).join('');
        }
        container.innerHTML = html;
    } catch {
        container.innerHTML = '<div class="empty-state">이력을 불러올 수 없습니다</div>';
    }
}

async function showActiveDiscounts() {
    const container = document.getElementById('mypageContent');
    container.innerHTML = '<div class="loading-text">불러오는 중...</div>';

    try {
        const data = await API.getActiveDiscounts();
        let html = `
            <div style="margin-bottom:12px;">
                <button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="loadMypage()">← 돌아가기</button>
                <h3 style="margin-top:12px;">내 회사 할인</h3>
            </div>
        `;

        if (!data.discounts || data.discounts.length === 0) {
            html += '<div class="empty-state">활성 할인이 없습니다</div>';
        } else {
            html += data.discounts.map(d => `
                <div class="store-card" onclick="openStoreDetail(${d.store_id})">
                    <div class="card-info">
                        <div class="card-name">${d.store_name || '매장'}</div>
                        <div class="card-meta">${d.description}</div>
                    </div>
                    <div class="card-discount">${d.discount_value}%</div>
                </div>
            `).join('');
        }
        container.innerHTML = html;
    } catch {
        container.innerHTML = '<div class="empty-state">할인 정보를 불러올 수 없습니다</div>';
    }
}

function showEditProfile() {
    const user = API.getUser();
    if (!user) return;

    const container = document.getElementById('mypageContent');
    container.innerHTML = `
        <div style="margin-bottom:12px;">
            <button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="loadMypage()">← 돌아가기</button>
            <h3 style="margin-top:12px;">프로필 수정</h3>
        </div>
        <div class="profile-card">
            <form onsubmit="return handleUpdateProfile(event)">
                <div class="form-group">
                    <label>이름</label>
                    <input type="text" id="editName" value="${user.name || ''}" required>
                </div>
                <div class="form-group">
                    <label>전화번호</label>
                    <input type="tel" id="editPhone" value="${user.phone || ''}" placeholder="010-0000-0000">
                </div>
                <button type="submit" class="btn-primary btn-full">저장</button>
            </form>
        </div>
    `;
}

async function handleUpdateProfile(e) {
    e.preventDefault();
    try {
        const data = {
            name: document.getElementById('editName').value,
            phone: document.getElementById('editPhone').value,
        };
        const result = await API.updateProfile(data);
        API.setUser(result);
        showToast('프로필 수정 완료');
        loadMypage();
    } catch (err) {
        showToast(err.detail || '수정 실패');
    }
    return false;
}

/**
 * 절약 분석 - 사용 이력 기반 통계 및 차트
 */
let savingsPieChart = null;
let savingsLineChart = null;

async function loadSavingsAnalytics() {
    const container = document.getElementById('savingsAnalytics');
    if (!container) return;

    try {
        const data = await API.getUsageHistory();
        const items = data.items || [];

        if (items.length === 0) {
            container.innerHTML = '';
            return;
        }

        // 통계 계산
        const stats = computeSavingsStats(items);

        // 요약 카드 + 차트 컨테이너 렌더링
        container.innerHTML = `
            <div class="savings-section">
                <h3>절약 분석</h3>
                <div class="savings-stats-grid">
                    <div class="savings-stat-card">
                        <div class="savings-stat-value">${formatCurrency(stats.monthlySavings)}</div>
                        <div class="savings-stat-label">이번달 절약</div>
                    </div>
                    <div class="savings-stat-card">
                        <div class="savings-stat-value">${formatCurrency(stats.totalSavings)}</div>
                        <div class="savings-stat-label">총 절약</div>
                    </div>
                    <div class="savings-stat-card">
                        <div class="savings-stat-value">${stats.usageCount}회</div>
                        <div class="savings-stat-label">사용 횟수</div>
                    </div>
                </div>
                <div class="savings-chart-card">
                    <h4>카테고리별 절약</h4>
                    <canvas id="savingsPieChart"></canvas>
                </div>
                <div class="savings-chart-card">
                    <h4>월별 절약 추이</h4>
                    <canvas id="savingsLineChart"></canvas>
                </div>
            </div>
        `;

        // 차트 렌더링
        renderSavingsPieChart(stats.byCategory);
        renderSavingsLineChart(stats.monthlyTrend);
    } catch (e) {
        console.error('Savings analytics error:', e);
        container.innerHTML = '';
    }
}

function computeSavingsStats(items) {
    const now = new Date();
    const currentMonth = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');

    let totalSavings = 0;
    let monthlySavings = 0;
    const byCategory = {};
    const monthlyTrend = {};

    items.forEach(item => {
        // saved_amount가 있으면 사용, 없으면 discount_value 기반 추정 (할인율 * 1000원 기본 단가)
        const saved = item.saved_amount || (item.discount_value || 0) * 100;
        totalSavings += saved;

        // 이번달 절약
        const usedAt = item.used_at || '';
        const itemMonth = usedAt.substring(0, 7); // "YYYY-MM"
        if (itemMonth === currentMonth) {
            monthlySavings += saved;
        }

        // 카테고리별
        const cat = item.category || item.store_category || '기타';
        byCategory[cat] = (byCategory[cat] || 0) + saved;

        // 월별 추이
        if (itemMonth) {
            monthlyTrend[itemMonth] = (monthlyTrend[itemMonth] || 0) + saved;
        }
    });

    return {
        totalSavings,
        monthlySavings,
        usageCount: items.length,
        byCategory,
        monthlyTrend,
    };
}

function formatCurrency(amount) {
    if (amount >= 10000) {
        return (amount / 10000).toFixed(1).replace(/\.0$/, '') + '만원';
    }
    return amount.toLocaleString('ko-KR') + '원';
}

function renderSavingsPieChart(byCategory) {
    const canvas = document.getElementById('savingsPieChart');
    if (!canvas || typeof Chart === 'undefined') return;

    // 이전 차트 파기
    if (savingsPieChart) {
        savingsPieChart.destroy();
        savingsPieChart = null;
    }

    const labels = Object.keys(byCategory).map(cat => {
        const catMap = {
            food: '음식점', cafe: '카페', shopping: '쇼핑',
            convenience: '편의점', entertainment: '엔터', general: '기타'
        };
        return catMap[cat] || cat;
    });
    const values = Object.values(byCategory);
    const colors = ['#FF6B35', '#4285f4', '#34C759', '#FF9500', '#AF52DE', '#FF3B30', '#5AC8FA', '#FFB800'];

    savingsPieChart = new Chart(canvas, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 2,
                borderColor: '#fff',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: { size: 11 },
                        padding: 12,
                        usePointStyle: true,
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const val = ctx.parsed;
                            return ctx.label + ': ' + formatCurrency(val);
                        }
                    }
                }
            }
        }
    });
}

function renderSavingsLineChart(monthlyTrend) {
    const canvas = document.getElementById('savingsLineChart');
    if (!canvas || typeof Chart === 'undefined') return;

    // 이전 차트 파기
    if (savingsLineChart) {
        savingsLineChart.destroy();
        savingsLineChart = null;
    }

    // 월별 정렬 (최근 6개월)
    const sortedMonths = Object.keys(monthlyTrend).sort();
    const recentMonths = sortedMonths.slice(-6);
    const labels = recentMonths.map(m => {
        const parts = m.split('-');
        return parts[1] + '월';
    });
    const values = recentMonths.map(m => monthlyTrend[m]);

    savingsLineChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '월별 절약액',
                data: values,
                borderColor: '#FF6B35',
                backgroundColor: 'rgba(255, 107, 53, 0.1)',
                borderWidth: 2.5,
                pointBackgroundColor: '#FF6B35',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                fill: true,
                tension: 0.3,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            return '절약: ' + formatCurrency(ctx.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        font: { size: 10 },
                        callback: function(val) { return formatCurrency(val); }
                    },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                },
                x: {
                    ticks: { font: { size: 11 } },
                    grid: { display: false }
                }
            }
        }
    });
}

// === 할인 코드 사용 내역 (Redemption) ===

async function loadRedemptionStats() {
    const container = document.getElementById('redemptionStatsSection');
    if (!container) return;

    try {
        const stats = await API.getRedemptionStats();

        if (stats.count === 0) {
            container.innerHTML = '';
            return;
        }

        const catMap = {
            food: '음식점', cafe: '카페', shopping: '쇼핑',
            convenience: '편의점', entertainment: '엔터', general: '기타'
        };

        // 카테고리별 최다 절약 계산
        let topCategory = '';
        let topCategoryValue = 0;
        for (const [cat, val] of Object.entries(stats.by_category || {})) {
            if (val > topCategoryValue) {
                topCategoryValue = val;
                topCategory = catMap[cat] || cat;
            }
        }

        container.innerHTML =
            '<div class="redemption-stats-section">'
            + '<h3>코드 사용 절약 현황</h3>'
            + '<div class="savings-stats-grid">'
            + '<div class="savings-stat-card">'
            + '<div class="savings-stat-value">' + formatCurrency(stats.this_month || 0) + '</div>'
            + '<div class="savings-stat-label">이번달 절약</div>'
            + '</div>'
            + '<div class="savings-stat-card">'
            + '<div class="savings-stat-value">' + formatCurrency(stats.total_saved || 0) + '</div>'
            + '<div class="savings-stat-label">총 절약</div>'
            + '</div>'
            + '<div class="savings-stat-card">'
            + '<div class="savings-stat-value">' + (stats.count || 0) + '회</div>'
            + '<div class="savings-stat-label">코드 사용</div>'
            + '</div>'
            + '</div>'
            + (topCategory
                ? '<div style="text-align:center;margin-top:8px;font-size:0.8rem;color:#666;">'
                  + '가장 많이 절약한 카테고리: <strong>' + topCategory + '</strong> ('
                  + formatCurrency(topCategoryValue) + ')</div>'
                : '')
            + '</div>';
    } catch (e) {
        console.error('Redemption stats error:', e);
        container.innerHTML = '';
    }
}

async function loadRedemptionHistoryPreview() {
    const container = document.getElementById('redemptionHistorySection');
    if (!container) return;

    try {
        const data = await API.getRedemptionHistory();
        const items = data.items || [];

        if (items.length === 0) {
            container.innerHTML = '';
            return;
        }

        // 최근 3건만 미리보기
        const preview = items.slice(0, 3);

        let html = '<div class="redemption-history-preview">'
            + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            + '<h4 style="margin:0;font-size:0.95rem;">최근 코드 사용</h4>'
            + '<a href="#" onclick="showRedemptionHistory();return false;" style="font-size:0.8rem;color:#4285f4;text-decoration:none;">전체보기</a>'
            + '</div>';

        html += preview.map(function(item) {
            const usedDate = item.used_at ? item.used_at.split('T')[0] : '';
            return '<div class="redemption-history-item">'
                + '<div style="flex:1;">'
                + '<div style="font-weight:600;font-size:0.88rem;">' + (item.store_name || '매장') + '</div>'
                + '<div style="font-size:0.78rem;color:#888;">' + (item.discount_description || '') + '</div>'
                + '<div style="font-size:0.72rem;color:#aaa;">' + usedDate + '</div>'
                + '</div>'
                + '<div style="text-align:right;">'
                + '<div style="font-weight:700;color:#FF6B35;">' + (item.discount_value || 0) + '% OFF</div>'
                + '<div style="font-size:0.75rem;color:#34C759;">-' + formatCurrency(item.saved_amount || 0) + '</div>'
                + '</div>'
                + '</div>';
        }).join('');

        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        console.error('Redemption history preview error:', e);
        container.innerHTML = '';
    }
}

async function showRedemptionHistory() {
    const container = document.getElementById('mypageContent');
    container.innerHTML = '<div class="loading-text">불러오는 중...</div>';

    try {
        const [historyData, statsData] = await Promise.all([
            API.getRedemptionHistory(),
            API.getRedemptionStats(),
        ]);

        const items = historyData.items || [];

        const catMap = {
            food: '음식점', cafe: '카페', shopping: '쇼핑',
            convenience: '편의점', entertainment: '엔터', general: '기타'
        };

        let html = '<div style="margin-bottom:12px;">'
            + '<button class="btn-primary" style="font-size:0.8rem;padding:6px 12px;" onclick="loadMypage()">← 돌아가기</button>'
            + '<h3 style="margin-top:12px;">할인 코드 사용 내역</h3>'
            + '</div>';

        // 통계 요약
        html += '<div class="savings-stats-grid" style="margin-bottom:16px;">'
            + '<div class="savings-stat-card">'
            + '<div class="savings-stat-value">' + formatCurrency(statsData.total_saved || 0) + '</div>'
            + '<div class="savings-stat-label">총 절약</div>'
            + '</div>'
            + '<div class="savings-stat-card">'
            + '<div class="savings-stat-value">' + formatCurrency(statsData.this_month || 0) + '</div>'
            + '<div class="savings-stat-label">이번달</div>'
            + '</div>'
            + '<div class="savings-stat-card">'
            + '<div class="savings-stat-value">' + (statsData.count || 0) + '회</div>'
            + '<div class="savings-stat-label">총 사용</div>'
            + '</div>'
            + '</div>';

        // 카테고리별 분석
        if (statsData.by_category && Object.keys(statsData.by_category).length > 0) {
            html += '<div class="profile-card" style="margin-bottom:12px;">'
                + '<h4 style="margin:0 0 8px;font-size:0.9rem;">카테고리별 절약</h4>';
            for (const [cat, val] of Object.entries(statsData.by_category)) {
                const catName = catMap[cat] || cat;
                const pct = statsData.total_saved > 0 ? Math.round((val / statsData.total_saved) * 100) : 0;
                html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:0.85rem;">'
                    + '<span>' + catName + '</span>'
                    + '<div style="display:flex;align-items:center;gap:8px;">'
                    + '<div style="width:80px;height:6px;background:#f0f0f0;border-radius:3px;overflow:hidden;">'
                    + '<div style="width:' + pct + '%;height:100%;background:#FF6B35;border-radius:3px;"></div>'
                    + '</div>'
                    + '<span style="font-weight:600;min-width:60px;text-align:right;">' + formatCurrency(val) + '</span>'
                    + '</div>'
                    + '</div>';
            }
            html += '</div>';
        }

        // 내역 리스트
        if (items.length === 0) {
            html += '<div class="empty-state">할인 코드 사용 내역이 없습니다</div>';
        } else {
            html += items.map(function(item) {
                const usedDate = item.used_at ? item.used_at.split('T')[0] : '';
                const usedTime = item.used_at ? item.used_at.split('T')[1]?.substring(0, 5) || '' : '';
                return '<div class="history-item">'
                    + '<div>'
                    + '<div class="history-store">' + (item.store_name || '매장') + '</div>'
                    + '<div class="history-desc">' + (item.discount_description || '') + '</div>'
                    + '<div class="history-date">' + usedDate + (usedTime ? ' ' + usedTime : '')
                    + ' | 코드: ' + (item.code || '') + '</div>'
                    + '</div>'
                    + '<div style="text-align:right;">'
                    + '<div class="history-amount">' + (item.discount_value || 0) + '% OFF</div>'
                    + '<div style="font-size:0.78rem;color:#34C759;font-weight:600;">-' + formatCurrency(item.saved_amount || 0) + '</div>'
                    + '</div>'
                    + '</div>';
            }).join('');
        }

        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div class="empty-state">내역을 불러올 수 없습니다</div>';
    }
}
