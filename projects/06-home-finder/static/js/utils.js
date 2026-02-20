/**
 * HomeFinder - Shared Utility Functions
 * 공통 유틸리티 함수 (formatPrice, formatDate, fetchWithTimeout)
 * 각 페이지에서 중복 정의되던 함수를 통합
 */

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
