/**
 * PromoMap 메인 앱 컨트롤러
 */

let currentTab = 'map';

function getCurrentTab() { return currentTab; }

function switchTab(tab) {
    currentTab = tab;

    // 모든 탭 비활성화
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`.nav-item[data-tab="${tab}"]`).classList.add('active');

    // 맵/패널 표시 토글
    const mapArea = document.getElementById('mapArea');
    const promoPanel = document.getElementById('promoPanel');
    const searchTab = document.getElementById('tabSearch');
    const favTab = document.getElementById('tabFavorites');
    const myTab = document.getElementById('tabMypage');

    mapArea.style.display = tab === 'map' ? 'block' : 'none';
    promoPanel.style.display = tab === 'map' ? 'block' : 'none';
    searchTab.style.display = tab === 'search' ? 'block' : 'none';
    favTab.style.display = tab === 'favorites' ? 'block' : 'none';
    myTab.style.display = tab === 'mypage' ? 'block' : 'none';

    // 탭별 데이터 로드
    if (tab === 'favorites') loadFavorites();
    if (tab === 'mypage') loadMypage();
    if (tab === 'map' && kakaoMap) {
        setTimeout(() => kakaoMap.relayout(), 100);
    }
}

function refreshCurrentTab() {
    switchTab(currentTab);
}

// 바텀시트 토글
function initPromoPanel() {
    const handle = document.getElementById('promoHandle');
    handle.addEventListener('click', () => {
        document.getElementById('promoPanel').classList.toggle('collapsed');
    });
}

// 앱 초기화
function initApp() {
    // 스켈레톤 제거
    setTimeout(() => {
        document.getElementById('skeleton').style.display = 'none';
        document.getElementById('app').style.display = 'block';

        // 카카오맵 초기화
        initKakaoMap();

        // 검색 초기화
        initSearch();

        // 바텀시트 초기화
        initPromoPanel();

        // 인증 상태 확인
        updateAuthUI();

        // 30초 주기 갱신
        setInterval(() => {
            if (currentTab === 'map') loadNearbyStores();
        }, 30000);
    }, 500);
}

// DOM 로드 후 실행
document.addEventListener('DOMContentLoaded', initApp);
