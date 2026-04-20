/**
 * HomeFinder - Shared Utility Functions
 * 공통 유틸리티 함수 (formatPrice, formatDate, formatArea, 대출계산, fetchWithTimeout)
 * 각 페이지에서 중복 정의되던 함수를 통합
 */

// ──── 평/㎡ 전환 상태 ────
var _areaUnitPyeong = false; // false=㎡, true=평

/**
 * 가격 포맷 (원 -> 억/만 표시)
 * @param {number} krw - 원화 금액
 * @returns {string} 포맷된 가격 문자열
 */
function formatPrice(krw) {
    if (!krw) return '가격미정';
    const eok = Math.floor(krw / 100000000);
    const man = Math.floor((krw % 100000000) / 10000);
    if (eok > 0 && man > 0) return eok + '억 ' + man.toLocaleString() + '만';
    if (eok > 0) return eok + '억';
    if (man > 0) return man.toLocaleString() + '만';
    return krw.toLocaleString() + '원';
}

/**
 * 날짜 포맷 (ISO -> YYYY.MM.DD)
 * @param {string} iso - ISO 날짜 문자열
 * @returns {string} 포맷된 날짜
 */
function formatDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '-';
    return d.getFullYear() + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + String(d.getDate()).padStart(2, '0');
}

/**
 * 면적 포맷 (㎡ + 평 병기)
 * @param {number} m2 - 제곱미터 면적
 * @param {boolean} [compact] - true이면 현재 선택된 단위만 표시
 * @returns {string} 포맷된 면적 문자열
 */
function formatArea(m2, compact) {
    if (!m2) return '-';
    var pyeong = (m2 / 3.3058).toFixed(0);
    if (compact && _areaUnitPyeong) {
        return pyeong + '평';
    }
    if (compact) {
        return m2 + '㎡';
    }
    return m2 + '㎡ (' + pyeong + '평)';
}

/**
 * ㎡ → 평 변환
 */
function m2ToPyeong(m2) {
    return m2 ? (m2 / 3.3058).toFixed(1) : 0;
}

/**
 * 평 → ㎡ 변환
 */
function pyeongToM2(pyeong) {
    return pyeong ? (pyeong * 3.3058).toFixed(1) : 0;
}

/**
 * 면적 단위 토글 (㎡ ↔ 평)
 */
function toggleAreaUnit() {
    _areaUnitPyeong = !_areaUnitPyeong;
    var btn = document.getElementById('areaUnitToggle');
    if (btn) {
        btn.textContent = _areaUnitPyeong ? '평' : '㎡';
        btn.title = _areaUnitPyeong ? '㎡ 단위로 전환' : '평 단위로 전환';
    }
    // Dispatch custom event so pages can re-render
    document.dispatchEvent(new CustomEvent('areaUnitChanged', { detail: { pyeong: _areaUnitPyeong } }));
}

/**
 * 타임아웃이 있는 fetch 래퍼
 * @param {string} url - 요청 URL
 * @param {object} options - fetch 옵션
 * @param {number} timeout - 타임아웃 (ms), 기본 5000ms
 * @returns {Promise<Response>}
 */
function fetchWithTimeout(url, options, timeout) {
    if (timeout === undefined) timeout = 5000;
    return Promise.race([
        fetch(url, options),
        new Promise(function(_, reject) {
            setTimeout(function() {
                reject(new Error('요청 시간이 초과되었습니다. 네트워크 상태를 확인해 주세요.'));
            }, timeout);
        })
    ]);
}

// ──────────────── 대출 계산기 (Mortgage Calculator) ────────────────

/**
 * 대출 한도 계산 (LTV 규제 반영)
 * 9억 이하: 70%, 9억 초과분: 50% (2024년 기준 일반적 규제)
 */
function calcLoanLimit(priceKrw) {
    if (!priceKrw || priceKrw <= 0) return 0;
    var threshold = 900000000; // 9억
    if (priceKrw <= threshold) {
        return Math.floor(priceKrw * 0.7);
    }
    var loanUnder9 = Math.floor(threshold * 0.7);
    var loanOver9 = Math.floor((priceKrw - threshold) * 0.5);
    return loanUnder9 + loanOver9;
}

/**
 * 월 상환액 계산 (원리금 균등상환)
 * @param {number} principal - 대출 원금 (원)
 * @param {number} annualRate - 연이율 (%, 예: 3.5)
 * @param {number} years - 상환 기간 (년)
 * @returns {number} 월 상환액 (원)
 */
function calcMonthlyPayment(principal, annualRate, years) {
    if (!principal || principal <= 0) return 0;
    if (!annualRate || annualRate <= 0) return Math.round(principal / (years * 12));
    var monthlyRate = annualRate / 100 / 12;
    var numPayments = years * 12;
    var payment = principal * monthlyRate * Math.pow(1 + monthlyRate, numPayments)
                  / (Math.pow(1 + monthlyRate, numPayments) - 1);
    return Math.round(payment);
}

/**
 * DSR 계산 (연간 원리금 상환액 / 연 소득)
 * @param {number} monthlyPayment - 월 상환액
 * @param {number} annualIncome - 연 소득 (원)
 * @returns {number} DSR 비율 (%)
 */
function calcDSR(monthlyPayment, annualIncome) {
    if (!annualIncome || annualIncome <= 0) return 0;
    return ((monthlyPayment * 12) / annualIncome * 100);
}

/**
 * 대출 계산기 모달 업데이트
 */
function updateMortgageCalc() {
    var priceEl = document.getElementById('mc-price');
    var downEl = document.getElementById('mc-downpayment');
    var rateEl = document.getElementById('mc-rate');
    var yearsEl = document.getElementById('mc-years');
    var incomeEl = document.getElementById('mc-income');

    if (!priceEl) return;

    var priceKrw = Math.round(parseFloat(priceEl.value || 0) * 100000000);
    var downPct = parseFloat(downEl.value || 30);
    var rate = parseFloat(rateEl.value || 3.5);
    var years = parseInt(yearsEl.value || 30);
    var incomeKrw = Math.round(parseFloat(incomeEl.value || 0) * 10000 * 12); // 월소득(만) → 연(원)

    // LTV limit
    var ltvLimit = calcLoanLimit(priceKrw);
    var downKrw = Math.round(priceKrw * downPct / 100);
    var loanKrw = priceKrw - downKrw;

    // Cap by LTV
    var ltvCapped = false;
    if (loanKrw > ltvLimit) {
        loanKrw = ltvLimit;
        downKrw = priceKrw - loanKrw;
        ltvCapped = true;
    }

    var ltvPct = priceKrw > 0 ? (loanKrw / priceKrw * 100) : 0;
    var monthly = calcMonthlyPayment(loanKrw, rate, years);
    var totalInterest = (monthly * years * 12) - loanKrw;
    var dsrPct = incomeKrw > 0 ? calcDSR(monthly, incomeKrw) : 0;

    // Update display
    document.getElementById('mc-ltv-limit').textContent = formatPrice(ltvLimit);
    document.getElementById('mc-loan-amount').textContent = formatPrice(loanKrw);
    document.getElementById('mc-down-amount').textContent = formatPrice(downKrw);
    document.getElementById('mc-ltv-pct').textContent = ltvPct.toFixed(1) + '%';
    document.getElementById('mc-monthly').textContent = formatPrice(monthly);
    document.getElementById('mc-total-interest').textContent = formatPrice(totalInterest > 0 ? totalInterest : 0);

    var dsrEl = document.getElementById('mc-dsr');
    if (incomeKrw > 0) {
        dsrEl.textContent = dsrPct.toFixed(1) + '%';
        dsrEl.className = dsrPct > 40 ? 'fw-bold text-danger' : (dsrPct > 30 ? 'fw-bold text-warning' : 'fw-bold text-success');
    } else {
        dsrEl.textContent = '-';
        dsrEl.className = 'fw-bold text-muted';
    }

    var warnEl = document.getElementById('mc-ltv-warn');
    if (warnEl) {
        warnEl.style.display = ltvCapped ? 'block' : 'none';
    }
    var dsrWarnEl = document.getElementById('mc-dsr-warn');
    if (dsrWarnEl) {
        dsrWarnEl.style.display = dsrPct > 40 ? 'block' : 'none';
    }
}

/**
 * 대출계산 모달 열기 (매매가 자동 입력)
 */
function openMortgageCalc(priceKrw) {
    var priceEl = document.getElementById('mc-price');
    if (priceEl && priceKrw) {
        priceEl.value = (priceKrw / 100000000).toFixed(1);
    }
    updateMortgageCalc();
    var modalEl = document.getElementById('mortgageModal');
    if (modalEl) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }
}

// ──────────────── Score badge helper ────────────────

function getScoreBadgeClass(score) {
    if (score >= 70) return 'bg-success';
    if (score >= 45) return 'bg-primary';
    return 'bg-secondary';
}

function timeAgo(iso) {
    if (!iso) return '';
    var now = new Date();
    var d = new Date(iso);
    var diff = Math.floor((now - d) / 1000);
    if (diff < 60) return '방금';
    if (diff < 3600) return Math.floor(diff / 60) + '분 전';
    if (diff < 86400) return Math.floor(diff / 3600) + '시간 전';
    return Math.floor(diff / 86400) + '일 전';
}
