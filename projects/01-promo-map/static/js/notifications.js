/**
 * PromoMap 지오펜스 알림 시스템
 *
 * - 위치 변화 감지 (watchPosition, 30초 간격 전송)
 * - 알림 벨 아이콘 + 읽지 않은 수 배지
 * - 알림 드롭다운 패널 (카드형)
 * - 토스트 알림 (고우선순위 근처 딜)
 * - 알림 클릭 -> 지도에서 매장 이동
 * - 설정 패널 (반경, 방해금지 시간)
 */

const NotificationManager = (() => {
    'use strict';

    // === 상태 ===
    let _watchId = null;
    let _lastSendTime = 0;
    let _lastLat = null;
    let _lastLng = null;
    let _unreadCount = 0;
    let _notifications = [];
    let _panelOpen = false;
    let _settingsOpen = false;
    let _preferences = null;
    let _pollTimer = null;

    const SEND_INTERVAL_MS = 30000;     // 30초
    const MIN_MOVE_METERS = 20;         // 최소 이동 거리(m)
    const POLL_INTERVAL_MS = 60000;     // 미읽은 알림 폴링 주기 60초
    const HIGH_PRIORITY_THRESHOLD = 80; // 토스트 표시 기준 우선순위

    // === 카테고리 아이콘 매핑 ===
    const CATEGORY_ICONS = {
        food: '\uD83C\uDF5C', cafe: '\u2615', shopping: '\uD83D\uDECD\uFE0F',
        convenience: '\uD83C\uDFEA', entertainment: '\uD83C\uDFAC', general: '\uD83C\uDFE2',
    };

    // === 유틸 ===

    function _haversine(lat1, lng1, lat2, lng2) {
        const R = 6371000;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLng = (lng2 - lng1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) ** 2
            + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180)
            * Math.sin(dLng / 2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }

    function _timeAgo(isoStr) {
        if (!isoStr) return '';
        const diff = Date.now() - new Date(isoStr).getTime();
        const min = Math.floor(diff / 60000);
        if (min < 1) return '방금 전';
        if (min < 60) return min + '분 전';
        const hrs = Math.floor(min / 60);
        if (hrs < 24) return hrs + '시간 전';
        return Math.floor(hrs / 24) + '일 전';
    }

    function _escHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // === 벨 아이콘 UI 주입 ===

    function _injectBellUI() {
        // 벨 아이콘은 top-bar 안에 검색 버튼 앞에 삽입
        const topBar = document.querySelector('.top-bar');
        if (!topBar || document.getElementById('notifBellBtn')) return;

        const bellBtn = document.createElement('button');
        bellBtn.id = 'notifBellBtn';
        bellBtn.className = 'notif-bell-btn';
        bellBtn.setAttribute('aria-label', '알림');
        bellBtn.innerHTML =
            '<svg class="notif-bell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
            + '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>'
            + '<path d="M13.73 21a2 2 0 0 1-3.46 0"/>'
            + '</svg>'
            + '<span class="notif-badge" id="notifBadge" style="display:none;">0</span>';
        bellBtn.addEventListener('click', _togglePanel);

        // filter-btn (검색 버튼) 앞에 삽입
        const searchBtn = document.getElementById('searchBtn');
        if (searchBtn) {
            topBar.insertBefore(bellBtn, searchBtn);
        } else {
            topBar.appendChild(bellBtn);
        }

        // 알림 드롭다운 패널
        const panel = document.createElement('div');
        panel.id = 'notifPanel';
        panel.className = 'notif-panel';
        panel.style.display = 'none';
        panel.innerHTML =
            '<div class="notif-panel-header">'
            + '  <span class="notif-panel-title">알림</span>'
            + '  <div class="notif-panel-actions">'
            + '    <button class="notif-action-btn" id="notifSettingsBtn" title="알림 설정">'
            + '      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">'
            + '        <circle cx="12" cy="12" r="3"/>'
            + '        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
            + '      </svg>'
            + '    </button>'
            + '    <button class="notif-action-btn" id="notifReadAllBtn" title="모두 읽음">'
            + '      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">'
            + '        <polyline points="9 11 12 14 22 4"/>'
            + '        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'
            + '      </svg>'
            + '    </button>'
            + '  </div>'
            + '</div>'
            + '<div class="notif-panel-body" id="notifPanelBody">'
            + '  <div class="notif-empty">알림이 없습니다</div>'
            + '</div>';
        document.getElementById('app').appendChild(panel);

        // 설정 패널
        const settings = document.createElement('div');
        settings.id = 'notifSettingsPanel';
        settings.className = 'notif-settings-panel';
        settings.style.display = 'none';
        settings.innerHTML = _buildSettingsHtml();
        document.getElementById('app').appendChild(settings);

        // 이벤트 바인딩
        document.getElementById('notifSettingsBtn').addEventListener('click', function(e) {
            e.stopPropagation();
            _toggleSettings();
        });
        document.getElementById('notifReadAllBtn').addEventListener('click', function(e) {
            e.stopPropagation();
            _markAllRead();
        });

        // 패널 외부 클릭시 닫기
        document.addEventListener('click', function(e) {
            if (_panelOpen && !panel.contains(e.target) && e.target !== bellBtn && !bellBtn.contains(e.target)) {
                _closePanel();
            }
        });
    }

    function _buildSettingsHtml() {
        return '<div class="notif-settings-header">'
            + '  <span class="notif-settings-title">알림 설정</span>'
            + '  <button class="notif-settings-close" id="notifSettingsClose">&times;</button>'
            + '</div>'
            + '<div class="notif-settings-body">'
            // 활성화 토글
            + '  <div class="notif-setting-row">'
            + '    <span class="notif-setting-label">알림 받기</span>'
            + '    <label class="notif-toggle">'
            + '      <input type="checkbox" id="notifEnabled" checked />'
            + '      <span class="notif-toggle-slider"></span>'
            + '    </label>'
            + '  </div>'
            // 반경 슬라이더
            + '  <div class="notif-setting-group">'
            + '    <div class="notif-setting-row">'
            + '      <span class="notif-setting-label">알림 반경</span>'
            + '      <span class="notif-setting-value" id="radiusValue">500m</span>'
            + '    </div>'
            + '    <input type="range" class="notif-slider" id="notifRadius" min="100" max="2000" step="100" value="500" />'
            + '    <div class="notif-slider-labels"><span>100m</span><span>2km</span></div>'
            + '  </div>'
            // 방해금지 시간
            + '  <div class="notif-setting-group">'
            + '    <span class="notif-setting-label">방해금지 시간</span>'
            + '    <div class="notif-quiet-hours">'
            + '      <input type="time" id="quietStart" value="22:00" class="notif-time-input" />'
            + '      <span class="notif-quiet-sep">~</span>'
            + '      <input type="time" id="quietEnd" value="08:00" class="notif-time-input" />'
            + '    </div>'
            + '  </div>'
            // 일일 한도
            + '  <div class="notif-setting-group">'
            + '    <div class="notif-setting-row">'
            + '      <span class="notif-setting-label">일일 알림 한도</span>'
            + '      <span class="notif-setting-value" id="dailyLimitValue">50개</span>'
            + '    </div>'
            + '    <input type="range" class="notif-slider" id="notifDailyLimit" min="5" max="100" step="5" value="50" />'
            + '    <div class="notif-slider-labels"><span>5개</span><span>100개</span></div>'
            + '  </div>'
            // 카테고리 필터
            + '  <div class="notif-setting-group">'
            + '    <span class="notif-setting-label">알림 카테고리</span>'
            + '    <div class="notif-category-toggles" id="notifCategoryToggles">'
            + '      <label class="notif-cat-chip"><input type="checkbox" value="food" checked /><span>\uD83C\uDF5C 음식점</span></label>'
            + '      <label class="notif-cat-chip"><input type="checkbox" value="cafe" checked /><span>\u2615 카페</span></label>'
            + '      <label class="notif-cat-chip"><input type="checkbox" value="shopping" checked /><span>\uD83D\uDECD\uFE0F 쇼핑</span></label>'
            + '      <label class="notif-cat-chip"><input type="checkbox" value="convenience" checked /><span>\uD83C\uDFEA 편의점</span></label>'
            + '      <label class="notif-cat-chip"><input type="checkbox" value="entertainment" checked /><span>\uD83C\uDFAC 엔터</span></label>'
            + '      <label class="notif-cat-chip"><input type="checkbox" value="general" checked /><span>\uD83C\uDFE2 기타</span></label>'
            + '    </div>'
            + '  </div>'
            // 저장 버튼
            + '  <button class="btn-primary btn-full" id="notifSaveSettings">설정 저장</button>'
            + '</div>';
    }

    // === 패널 토글 ===

    function _togglePanel() {
        if (_panelOpen) {
            _closePanel();
        } else {
            _openPanel();
        }
    }

    function _openPanel() {
        const panel = document.getElementById('notifPanel');
        if (!panel) return;
        _closeSettings();
        panel.style.display = 'block';
        _panelOpen = true;
        _loadUnread();
    }

    function _closePanel() {
        const panel = document.getElementById('notifPanel');
        if (!panel) return;
        panel.style.display = 'none';
        _panelOpen = false;
        _closeSettings();
    }

    function _toggleSettings() {
        if (_settingsOpen) {
            _closeSettings();
        } else {
            _openSettings();
        }
    }

    function _openSettings() {
        const sp = document.getElementById('notifSettingsPanel');
        if (!sp) return;
        sp.style.display = 'block';
        _settingsOpen = true;
        _loadPreferences();

        // 이벤트 바인딩 (첫 열기 시)
        const closeBtn = document.getElementById('notifSettingsClose');
        // 기존 리스너 제거를 위해 새로 바인딩
        closeBtn.onclick = function() { _closeSettings(); };

        const radiusSlider = document.getElementById('notifRadius');
        radiusSlider.oninput = function() {
            const v = parseInt(this.value);
            document.getElementById('radiusValue').textContent = v >= 1000 ? (v / 1000) + 'km' : v + 'm';
        };

        const dailySlider = document.getElementById('notifDailyLimit');
        dailySlider.oninput = function() {
            document.getElementById('dailyLimitValue').textContent = this.value + '개';
        };

        document.getElementById('notifSaveSettings').onclick = _savePreferences;
    }

    function _closeSettings() {
        const sp = document.getElementById('notifSettingsPanel');
        if (!sp) return;
        sp.style.display = 'none';
        _settingsOpen = false;
    }

    // === 배지 업데이트 ===

    function _updateBadge(count) {
        _unreadCount = count;
        const badge = document.getElementById('notifBadge');
        if (!badge) return;
        if (count > 0) {
            badge.style.display = 'flex';
            badge.textContent = count > 99 ? '99+' : String(count);
        } else {
            badge.style.display = 'none';
        }
    }

    // === 알림 목록 로드 ===

    async function _loadUnread() {
        if (!API.isLoggedIn()) {
            _renderNotifications([]);
            _updateBadge(0);
            return;
        }
        try {
            const data = await API.getUnreadNotifications(50);
            _notifications = data.notifications || [];
            _updateBadge(data.count || 0);
            _renderNotifications(_notifications);
        } catch (err) {
            console.error('Notification load error:', err);
        }
    }

    function _renderNotifications(items) {
        const body = document.getElementById('notifPanelBody');
        if (!body) return;

        if (!API.isLoggedIn()) {
            body.innerHTML =
                '<div class="notif-empty">'
                + '<p>로그인하면 주변 할인 알림을 받을 수 있습니다</p>'
                + '<button class="btn-primary" onclick="openAuthModal()" style="margin-top:8px;font-size:0.85rem;padding:8px 16px;">로그인</button>'
                + '</div>';
            return;
        }

        if (!items || items.length === 0) {
            body.innerHTML = '<div class="notif-empty">새로운 알림이 없습니다</div>';
            return;
        }

        body.innerHTML = items.map(function(n) {
            const catIcon = CATEGORY_ICONS[n.store_category] || CATEGORY_ICONS.general;
            const iconColor = n.store_icon_color || '#FF6B35';
            const iconLetter = n.store_icon_letter || 'S';
            const dist = n.distance_m ? Math.round(n.distance_m) + 'm' : '';
            const time = _timeAgo(n.created_at);
            const priorityClass = n.priority >= HIGH_PRIORITY_THRESHOLD ? ' notif-card-high' : '';

            return '<div class="notif-card' + priorityClass + '" data-id="' + n.id + '" data-store-id="' + n.store_id + '"'
                + ' data-lat="' + (n.store_lat || '') + '" data-lng="' + (n.store_lng || '') + '">'
                + '<div class="notif-card-icon" style="background:' + iconColor + ';">'
                + iconLetter
                + '</div>'
                + '<div class="notif-card-body">'
                + '  <div class="notif-card-title">' + _escHtml(n.title) + '</div>'
                + '  <div class="notif-card-desc">' + _escHtml(n.body || '') + '</div>'
                + '  <div class="notif-card-meta">'
                + '    <span class="notif-card-cat">' + catIcon + '</span>'
                + (dist ? '<span class="notif-card-dist">' + dist + '</span>' : '')
                + '    <span class="notif-card-time">' + time + '</span>'
                + '  </div>'
                + '</div>'
                + '<button class="notif-card-dismiss" data-dismiss-id="' + n.id + '" title="해제">&times;</button>'
                + '</div>';
        }).join('');

        // 카드 클릭 이벤트 (매장 이동)
        body.querySelectorAll('.notif-card').forEach(function(card) {
            card.addEventListener('click', function(e) {
                if (e.target.classList.contains('notif-card-dismiss')) return;
                const id = parseInt(card.dataset.id);
                const storeId = parseInt(card.dataset.storeId);
                const lat = parseFloat(card.dataset.lat);
                const lng = parseFloat(card.dataset.lng);
                _onNotificationClick(id, storeId, lat, lng);
            });
        });

        // 해제 버튼
        body.querySelectorAll('.notif-card-dismiss').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const id = parseInt(btn.dataset.dismissId);
                _dismissNotification(id, btn.closest('.notif-card'));
            });
        });
    }

    // === 알림 클릭 -> 매장 이동 ===

    function _onNotificationClick(notifId, storeId, lat, lng) {
        // 읽음 처리
        API.markNotificationRead(notifId).catch(function() {});

        // 알림 패널 닫기
        _closePanel();

        // 지도 탭으로 전환
        if (typeof switchTab === 'function') {
            switchTab('map');
        }

        // 지도 이동
        if (typeof kakaoMap !== 'undefined' && kakaoMap && lat && lng) {
            setTimeout(function() {
                var moveLatLng = new kakao.maps.LatLng(lat, lng);
                kakaoMap.setCenter(moveLatLng);
                kakaoMap.setLevel(3);
            }, 200);
        }

        // 매장 상세 열기
        if (typeof openStoreDetail === 'function' && storeId) {
            setTimeout(function() {
                openStoreDetail(storeId);
            }, 400);
        }

        // 배지 수 감소
        _updateBadge(Math.max(0, _unreadCount - 1));

        // 카드 제거 (UI 즉시 반영)
        var card = document.querySelector('.notif-card[data-id="' + notifId + '"]');
        if (card) {
            card.style.opacity = '0';
            card.style.transform = 'translateX(100%)';
            setTimeout(function() { card.remove(); }, 300);
        }
    }

    // === 알림 해제 ===

    async function _dismissNotification(id, cardEl) {
        try {
            await API.dismissNotification(id);
        } catch (err) {
            console.error('Dismiss error:', err);
        }
        _updateBadge(Math.max(0, _unreadCount - 1));
        if (cardEl) {
            cardEl.style.opacity = '0';
            cardEl.style.transform = 'translateX(100%)';
            setTimeout(function() {
                cardEl.remove();
                // 리스트가 비었으면 빈 상태 표시
                var body = document.getElementById('notifPanelBody');
                if (body && body.querySelectorAll('.notif-card').length === 0) {
                    body.innerHTML = '<div class="notif-empty">새로운 알림이 없습니다</div>';
                }
            }, 300);
        }
    }

    // === 모두 읽음 ===

    async function _markAllRead() {
        if (!API.isLoggedIn()) return;
        try {
            await API.markAllNotificationsRead();
            _updateBadge(0);
            _notifications = [];
            _renderNotifications([]);
            showToast('모든 알림을 읽음 처리했습니다');
        } catch (err) {
            console.error('Mark all read error:', err);
        }
    }

    // === 위치 감시 ===

    function _startGeolocationWatch() {
        if (!navigator.geolocation) return;
        if (_watchId !== null) return;

        _watchId = navigator.geolocation.watchPosition(
            function(pos) {
                var lat = pos.coords.latitude;
                var lng = pos.coords.longitude;
                var now = Date.now();

                // 최소 이동 거리 확인
                if (_lastLat !== null && _lastLng !== null) {
                    var moved = _haversine(_lastLat, _lastLng, lat, lng);
                    if (moved < MIN_MOVE_METERS && (now - _lastSendTime) < SEND_INTERVAL_MS) {
                        return;
                    }
                }

                // 시간 간격 확인
                if (now - _lastSendTime < SEND_INTERVAL_MS) return;

                _lastLat = lat;
                _lastLng = lng;
                _lastSendTime = now;

                _sendLocationCheck(lat, lng);
            },
            function(err) {
                console.warn('Geolocation watch error:', err.message);
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 15000 }
        );
    }

    function _stopGeolocationWatch() {
        if (_watchId !== null) {
            navigator.geolocation.clearWatch(_watchId);
            _watchId = null;
        }
    }

    async function _sendLocationCheck(lat, lng) {
        if (!API.isLoggedIn()) return;
        try {
            var data = await API.checkNotifications(lat, lng);
            var newNotifs = data.notifications || [];

            if (newNotifs.length > 0) {
                // 배지 업데이트
                _updateBadge(_unreadCount + newNotifs.length);

                // 고우선순위 알림은 토스트로 표시
                var topNotif = newNotifs[0]; // 이미 우선순위 정렬됨
                if (topNotif.priority >= HIGH_PRIORITY_THRESHOLD) {
                    _showNotifToast(topNotif);
                } else if (newNotifs.length >= 3) {
                    // 3개 이상이면 요약 토스트
                    showToast('주변에 ' + newNotifs.length + '건의 새 할인 알림!');
                }
            }
        } catch (err) {
            // 401 등은 무시 (비로그인)
            if (err && err.status !== 401) {
                console.error('Location check error:', err);
            }
        }
    }

    // === 토스트 알림 (고우선순위) ===

    function _showNotifToast(n) {
        // 기존 알림 토스트 제거
        var existing = document.querySelector('.notif-toast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.className = 'notif-toast';
        toast.innerHTML =
            '<div class="notif-toast-icon" style="background:' + (n.icon_color || n.store_icon_color || '#FF6B35') + ';">'
            + (n.icon_letter || n.store_icon_letter || 'S')
            + '</div>'
            + '<div class="notif-toast-body">'
            + '  <div class="notif-toast-title">' + _escHtml(n.title || '') + '</div>'
            + '  <div class="notif-toast-desc">' + _escHtml(n.body || '') + '</div>'
            + '</div>';

        toast.addEventListener('click', function() {
            toast.remove();
            var storeId = n.store_id;
            var lat = n.store_lat;
            var lng = n.store_lng;
            var notifId = n.id;
            _onNotificationClick(notifId, storeId, lat, lng);
        });

        document.body.appendChild(toast);
        setTimeout(function() {
            if (toast.parentNode) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(function() { toast.remove(); }, 300);
            }
        }, 5000);
    }

    // === 설정 로드/저장 ===

    async function _loadPreferences() {
        if (!API.isLoggedIn()) return;
        try {
            var data = await API.getNotificationPreferences();
            _preferences = data;
            _applyPreferencesToUI(data);
        } catch (err) {
            console.error('Load preferences error:', err);
        }
    }

    function _applyPreferencesToUI(pref) {
        var enabledEl = document.getElementById('notifEnabled');
        if (enabledEl) enabledEl.checked = pref.is_enabled !== false;

        var radiusEl = document.getElementById('notifRadius');
        if (radiusEl) {
            radiusEl.value = pref.max_radius_m || 500;
            var v = parseInt(radiusEl.value);
            document.getElementById('radiusValue').textContent = v >= 1000 ? (v / 1000) + 'km' : v + 'm';
        }

        var dailyEl = document.getElementById('notifDailyLimit');
        if (dailyEl) {
            dailyEl.value = pref.daily_limit || 50;
            document.getElementById('dailyLimitValue').textContent = dailyEl.value + '개';
        }

        var quietStartEl = document.getElementById('quietStart');
        if (quietStartEl) quietStartEl.value = pref.quiet_hours_start || '22:00';

        var quietEndEl = document.getElementById('quietEnd');
        if (quietEndEl) quietEndEl.value = pref.quiet_hours_end || '08:00';

        // 카테고리 체크박스
        var enabledCats = (pref.enabled_categories || '').split(',').map(function(c) { return c.trim(); }).filter(Boolean);
        var allCats = ['food', 'cafe', 'shopping', 'convenience', 'entertainment', 'general'];
        var boxes = document.querySelectorAll('#notifCategoryToggles input[type="checkbox"]');
        boxes.forEach(function(box) {
            // 빈 문자열이면 모두 활성
            if (enabledCats.length === 0) {
                box.checked = true;
            } else {
                box.checked = enabledCats.indexOf(box.value) !== -1;
            }
        });
    }

    async function _savePreferences() {
        if (!API.isLoggedIn()) {
            showToast('로그인이 필요합니다');
            return;
        }

        var isEnabled = document.getElementById('notifEnabled').checked;
        var radius = parseInt(document.getElementById('notifRadius').value);
        var dailyLimit = parseInt(document.getElementById('notifDailyLimit').value);
        var quietStart = document.getElementById('quietStart').value;
        var quietEnd = document.getElementById('quietEnd').value;

        // 선택된 카테고리
        var selectedCats = [];
        document.querySelectorAll('#notifCategoryToggles input[type="checkbox"]:checked').forEach(function(box) {
            selectedCats.push(box.value);
        });
        var allCats = ['food', 'cafe', 'shopping', 'convenience', 'entertainment', 'general'];
        // 모두 선택 = 빈 문자열 (필터 없음)
        var catStr = selectedCats.length === allCats.length ? '' : selectedCats.join(',');

        try {
            var result = await API.updateNotificationPreferences({
                is_enabled: isEnabled,
                max_radius_m: radius,
                daily_limit: dailyLimit,
                quiet_hours_start: quietStart,
                quiet_hours_end: quietEnd,
                enabled_categories: catStr,
            });
            _preferences = result.preferences;
            showToast('알림 설정이 저장되었습니다');
            setTimeout(function() { _closeSettings(); }, 500);
        } catch (err) {
            showToast(err.detail || '설정 저장 실패');
        }
    }

    // === 읽지 않은 알림 폴링 ===

    function _startPolling() {
        if (_pollTimer) return;
        _pollTimer = setInterval(function() {
            if (API.isLoggedIn()) {
                _loadUnreadCount();
            }
        }, POLL_INTERVAL_MS);
    }

    function _stopPolling() {
        if (_pollTimer) {
            clearInterval(_pollTimer);
            _pollTimer = null;
        }
    }

    async function _loadUnreadCount() {
        if (!API.isLoggedIn()) {
            _updateBadge(0);
            return;
        }
        try {
            var data = await API.getUnreadNotifications(1);
            _updateBadge(data.count || 0);
        } catch (err) {
            // 무시
        }
    }

    // === 스타일 주입 ===

    function _injectStyles() {
        if (document.getElementById('notif-styles')) return;
        var style = document.createElement('style');
        style.id = 'notif-styles';
        style.textContent = ''
            /* 벨 버튼 */
            + '.notif-bell-btn {'
            + '  position:relative; background:none; border:none; cursor:pointer;'
            + '  padding:6px; display:flex; align-items:center; justify-content:center;'
            + '  color:var(--text); transition:color 0.2s;'
            + '}'
            + '.notif-bell-btn:hover { color:var(--primary); }'
            + '.notif-bell-icon { width:24px; height:24px; }'
            + '.notif-badge {'
            + '  position:absolute; top:0; right:0;'
            + '  background:var(--danger); color:white;'
            + '  font-size:0.6rem; font-weight:700;'
            + '  min-width:16px; height:16px;'
            + '  border-radius:8px; padding:0 4px;'
            + '  display:flex; align-items:center; justify-content:center;'
            + '  border:2px solid white;'
            + '  animation:notifBadgePop 0.3s ease;'
            + '}'
            + '@keyframes notifBadgePop {'
            + '  0%{transform:scale(0)} 60%{transform:scale(1.3)} 100%{transform:scale(1)}'
            + '}'

            /* 알림 패널 */
            + '.notif-panel {'
            + '  position:fixed; top:var(--topbar-height); right:8px;'
            + '  width:340px; max-width:calc(100vw - 16px);'
            + '  max-height:calc(100vh - var(--topbar-height) - var(--nav-height) - 20px);'
            + '  background:white; border-radius:16px;'
            + '  box-shadow:0 8px 40px rgba(0,0,0,0.18);'
            + '  z-index:1500; overflow:hidden;'
            + '  display:flex; flex-direction:column;'
            + '  animation:notifSlideDown 0.2s ease;'
            + '}'
            + '@keyframes notifSlideDown {'
            + '  from{opacity:0;transform:translateY(-10px)} to{opacity:1;transform:translateY(0)}'
            + '}'
            + '.notif-panel-header {'
            + '  display:flex; justify-content:space-between; align-items:center;'
            + '  padding:14px 16px 10px; border-bottom:1px solid var(--border);'
            + '}'
            + '.notif-panel-title { font-weight:700; font-size:1rem; }'
            + '.notif-panel-actions { display:flex; gap:4px; }'
            + '.notif-action-btn {'
            + '  background:none; border:none; cursor:pointer; padding:4px;'
            + '  color:var(--text-secondary); border-radius:6px; transition:all 0.2s;'
            + '  display:flex; align-items:center; justify-content:center;'
            + '}'
            + '.notif-action-btn:hover { background:#f0f0f0; color:var(--primary); }'

            /* 패널 본문 */
            + '.notif-panel-body {'
            + '  flex:1; overflow-y:auto; padding:8px;'
            + '  max-height:400px;'
            + '}'
            + '.notif-empty {'
            + '  text-align:center; padding:40px 16px; color:var(--text-muted);'
            + '  font-size:0.88rem;'
            + '}'

            /* 알림 카드 */
            + '.notif-card {'
            + '  display:flex; align-items:flex-start; gap:10px;'
            + '  padding:10px 12px; border-radius:10px;'
            + '  cursor:pointer; transition:all 0.2s;'
            + '  position:relative; margin-bottom:2px;'
            + '}'
            + '.notif-card:hover { background:#f8f8f8; }'
            + '.notif-card-high { background:#FFF8F0; border-left:3px solid var(--primary); }'
            + '.notif-card-high:hover { background:#FFF0E0; }'
            + '.notif-card-icon {'
            + '  width:36px; height:36px; border-radius:8px; flex-shrink:0;'
            + '  display:flex; align-items:center; justify-content:center;'
            + '  font-size:14px; color:white; font-weight:700;'
            + '}'
            + '.notif-card-body { flex:1; min-width:0; }'
            + '.notif-card-title {'
            + '  font-weight:600; font-size:0.85rem; color:var(--text);'
            + '  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'
            + '}'
            + '.notif-card-desc {'
            + '  font-size:0.75rem; color:var(--text-secondary);'
            + '  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'
            + '  margin-top:2px;'
            + '}'
            + '.notif-card-meta {'
            + '  display:flex; align-items:center; gap:6px;'
            + '  margin-top:4px; font-size:0.7rem; color:var(--text-muted);'
            + '}'
            + '.notif-card-dist { font-weight:600; color:var(--primary); }'
            + '.notif-card-dismiss {'
            + '  position:absolute; top:8px; right:8px;'
            + '  background:none; border:none; cursor:pointer;'
            + '  font-size:1rem; color:var(--text-muted); padding:2px 4px;'
            + '  border-radius:4px; transition:all 0.2s; line-height:1;'
            + '}'
            + '.notif-card-dismiss:hover { color:var(--danger); background:#fff0f0; }'

            /* 토스트 알림 */
            + '.notif-toast {'
            + '  position:fixed; top:80px; right:16px;'
            + '  background:white; border-radius:12px;'
            + '  box-shadow:0 4px 24px rgba(0,0,0,0.18);'
            + '  padding:12px 16px; display:flex; align-items:center; gap:10px;'
            + '  z-index:3500; cursor:pointer; max-width:340px;'
            + '  border-left:4px solid var(--primary);'
            + '  animation:notifToastIn 0.3s ease;'
            + '  transition:opacity 0.3s, transform 0.3s;'
            + '}'
            + '@keyframes notifToastIn {'
            + '  from{opacity:0;transform:translateX(100%)} to{opacity:1;transform:translateX(0)}'
            + '}'
            + '.notif-toast-icon {'
            + '  width:32px; height:32px; border-radius:8px; flex-shrink:0;'
            + '  display:flex; align-items:center; justify-content:center;'
            + '  font-size:13px; color:white; font-weight:700;'
            + '}'
            + '.notif-toast-body { flex:1; min-width:0; }'
            + '.notif-toast-title { font-weight:600; font-size:0.85rem; }'
            + '.notif-toast-desc { font-size:0.75rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; }'

            /* 설정 패널 */
            + '.notif-settings-panel {'
            + '  position:fixed; top:var(--topbar-height); right:8px;'
            + '  width:340px; max-width:calc(100vw - 16px);'
            + '  max-height:calc(100vh - var(--topbar-height) - var(--nav-height) - 20px);'
            + '  background:white; border-radius:16px;'
            + '  box-shadow:0 8px 40px rgba(0,0,0,0.18);'
            + '  z-index:1600; overflow-y:auto;'
            + '  animation:notifSlideDown 0.2s ease;'
            + '}'
            + '.notif-settings-header {'
            + '  display:flex; justify-content:space-between; align-items:center;'
            + '  padding:14px 16px 10px; border-bottom:1px solid var(--border);'
            + '  position:sticky; top:0; background:white; z-index:1;'
            + '}'
            + '.notif-settings-title { font-weight:700; font-size:1rem; }'
            + '.notif-settings-close {'
            + '  background:none; border:none; font-size:1.4rem;'
            + '  color:var(--text-muted); cursor:pointer; padding:2px 6px;'
            + '}'
            + '.notif-settings-body { padding:16px; }'
            + '.notif-setting-row {'
            + '  display:flex; justify-content:space-between; align-items:center;'
            + '  margin-bottom:8px;'
            + '}'
            + '.notif-setting-group { margin-bottom:18px; }'
            + '.notif-setting-label { font-size:0.88rem; font-weight:600; color:var(--text); }'
            + '.notif-setting-value { font-size:0.85rem; font-weight:700; color:var(--primary); }'

            /* 토글 스위치 */
            + '.notif-toggle { position:relative; display:inline-block; width:44px; height:24px; }'
            + '.notif-toggle input { opacity:0; width:0; height:0; }'
            + '.notif-toggle-slider {'
            + '  position:absolute; cursor:pointer; inset:0;'
            + '  background:#ccc; border-radius:24px; transition:0.3s;'
            + '}'
            + '.notif-toggle-slider:before {'
            + '  content:""; position:absolute; height:18px; width:18px;'
            + '  left:3px; bottom:3px; background:white; border-radius:50%;'
            + '  transition:0.3s;'
            + '}'
            + '.notif-toggle input:checked + .notif-toggle-slider { background:var(--primary); }'
            + '.notif-toggle input:checked + .notif-toggle-slider:before { transform:translateX(20px); }'

            /* 슬라이더 */
            + '.notif-slider {'
            + '  width:100%; height:4px; -webkit-appearance:none; appearance:none;'
            + '  background:#e0e0e0; border-radius:2px; outline:none;'
            + '  margin:8px 0 4px;'
            + '}'
            + '.notif-slider::-webkit-slider-thumb {'
            + '  -webkit-appearance:none; appearance:none;'
            + '  width:20px; height:20px; border-radius:50%;'
            + '  background:var(--primary); cursor:pointer;'
            + '  box-shadow:0 1px 4px rgba(0,0,0,0.2);'
            + '}'
            + '.notif-slider::-moz-range-thumb {'
            + '  width:20px; height:20px; border-radius:50%; border:none;'
            + '  background:var(--primary); cursor:pointer;'
            + '  box-shadow:0 1px 4px rgba(0,0,0,0.2);'
            + '}'
            + '.notif-slider-labels {'
            + '  display:flex; justify-content:space-between;'
            + '  font-size:0.7rem; color:var(--text-muted);'
            + '}'

            /* 방해금지 시간 입력 */
            + '.notif-quiet-hours {'
            + '  display:flex; align-items:center; gap:8px; margin-top:8px;'
            + '}'
            + '.notif-time-input {'
            + '  flex:1; padding:8px 10px; border:1px solid #ddd;'
            + '  border-radius:8px; font-size:0.85rem; outline:none;'
            + '  text-align:center; transition:border-color 0.2s;'
            + '}'
            + '.notif-time-input:focus { border-color:var(--primary); }'
            + '.notif-quiet-sep { color:var(--text-muted); font-weight:600; }'

            /* 카테고리 토글 */
            + '.notif-category-toggles {'
            + '  display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;'
            + '}'
            + '.notif-cat-chip {'
            + '  display:flex; align-items:center; gap:4px;'
            + '  padding:5px 10px; border-radius:16px;'
            + '  background:#f0f0f0; font-size:0.78rem;'
            + '  cursor:pointer; transition:all 0.2s; user-select:none;'
            + '}'
            + '.notif-cat-chip input { display:none; }'
            + '.notif-cat-chip:has(input:checked) { background:var(--primary); color:white; }'
            /* fallback for browsers without :has */
            + '.notif-cat-chip.active { background:var(--primary); color:white; }'
        ;
        document.head.appendChild(style);
    }

    // :has() 폴백 - 체크박스 변경시 class 토글
    function _initCategoryChipFallback() {
        document.querySelectorAll('.notif-cat-chip input[type="checkbox"]').forEach(function(box) {
            function sync() {
                if (box.checked) {
                    box.parentElement.classList.add('active');
                } else {
                    box.parentElement.classList.remove('active');
                }
            }
            box.addEventListener('change', sync);
            sync();
        });
    }

    // === 공개 API ===

    function init() {
        _injectStyles();
        _injectBellUI();

        // :has() 폴백 초기화 (설정 패널이 열릴 때마다)
        var observer = new MutationObserver(function() {
            _initCategoryChipFallback();
        });
        var settingsPanel = document.getElementById('notifSettingsPanel');
        if (settingsPanel) {
            observer.observe(settingsPanel, { childList: true, subtree: true, attributes: true });
        }

        // 위치 감시 시작
        _startGeolocationWatch();

        // 폴링 시작
        _startPolling();

        // 초기 배지 업데이트
        _loadUnreadCount();
    }

    function destroy() {
        _stopGeolocationWatch();
        _stopPolling();
    }

    function refreshBadge() {
        _loadUnreadCount();
    }

    return {
        init: init,
        destroy: destroy,
        refreshBadge: refreshBadge,
    };
})();
