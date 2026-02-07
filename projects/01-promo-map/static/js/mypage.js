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

            <div class="menu-list">
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
