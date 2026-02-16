/**
 * HomeFinder - Chart.js 공통 유틸리티
 */

// 가격 포맷 (억/만)
function formatPrice(krw) {
    if (!krw) return '가격미정';
    const eok = Math.floor(krw / 100000000);
    const man = Math.floor((krw % 100000000) / 10000);
    if (eok > 0 && man > 0) return `${eok}억 ${man.toLocaleString()}만`;
    if (eok > 0) return `${eok}억`;
    return `${man.toLocaleString()}만`;
}

// 점수 색상
function getScoreColor(score) {
    if (score >= 80) return '#28a745';
    if (score >= 60) return '#007bff';
    if (score >= 40) return '#fd7e14';
    return '#dc3545';
}

// 점수 뱃지 class
function getScoreBadgeClass(score) {
    if (score >= 80) return 'bg-success';
    if (score >= 60) return 'bg-primary';
    if (score >= 40) return 'bg-warning text-dark';
    return 'bg-secondary';
}

// 시간 포맷 (몇 분 전, 몇 시간 전...)
function timeAgo(isoStr) {
    if (!isoStr) return '';
    const diff = Date.now() - new Date(isoStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return '방금 전';
    if (mins < 60) return `${mins}분 전`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}시간 전`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}일 전`;
    return new Date(isoStr).toLocaleDateString('ko-KR');
}

/**
 * 파이프라인 도넛 차트 렌더링
 */
function renderPipelineChart(canvasId, counts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    const labels = ['발견', '조사', '관심', '방문예정', '방문완료', '결정'];
    const colors = ['#6c757d', '#0dcaf0', '#ffc107', '#0d6efd', '#198754', '#dc3545'];
    const data = labels.map(l => counts[l] || 0);

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 2,
                borderColor: '#fff',
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 11 } } },
            },
        },
    });
}

/**
 * 가격 추이 라인 차트 렌더링
 */
function renderPriceLineChart(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets.map((ds, i) => ({
                label: ds.label,
                data: ds.data,
                borderColor: ds.color || ['#0d6efd', '#198754', '#fd7e14'][i % 3],
                backgroundColor: 'transparent',
                tension: 0.3,
                pointRadius: 2,
                borderWidth: 2,
            })),
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    ticks: {
                        callback: v => formatPrice(v),
                    },
                },
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${formatPrice(ctx.parsed.y)}`,
                    },
                },
                legend: { position: 'top', labels: { font: { size: 11 } } },
            },
        },
    });
}

/**
 * 레이더 차트 (매물 점수)
 */
function renderRadarChart(canvasId, labels, scores) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: '점수',
                data: scores,
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13,110,253,0.15)',
                pointBackgroundColor: '#0d6efd',
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    ticks: { stepSize: 20, font: { size: 10 } },
                    pointLabels: { font: { size: 12 } },
                },
            },
            plugins: { legend: { display: false } },
        },
    });
}

/**
 * 바 차트 (지역 비교)
 */
function renderBarChart(canvasId, labels, data1, data2, label1, label2) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: label1,
                    data: data1,
                    backgroundColor: 'rgba(13,110,253,0.7)',
                },
                {
                    label: label2,
                    data: data2,
                    backgroundColor: 'rgba(253,126,20,0.7)',
                },
            ],
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    ticks: {
                        callback: v => formatPrice(v),
                    },
                },
            },
            plugins: {
                legend: { position: 'top' },
            },
        },
    });
}
