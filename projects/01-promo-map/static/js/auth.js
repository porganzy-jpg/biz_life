/**
 * PromoMap 인증 관리
 */

function openAuthModal() {
    document.getElementById('authModal').style.display = 'flex';
    showLoginForm();
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

function showLoginForm() {
    document.getElementById('authModalTitle').textContent = '로그인';
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('registerForm').style.display = 'none';
}

function showRegisterForm() {
    document.getElementById('authModalTitle').textContent = '회원가입';
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('registerForm').style.display = 'block';
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const btn = e.target.querySelector('button[type="submit"]');

    if (btn) { btn.disabled = true; btn.textContent = '로그인 중...'; }
    try {
        const data = await API.login({ email, password });
        API.setTokens(data.access_token, data.refresh_token);
        API.setUser(data.user);
        closeAuthModal();
        showToast('로그인 성공!');
        updateAuthUI();
        refreshCurrentTab();
    } catch (err) {
        showToast(err.detail || '로그인 실패');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '로그인'; }
    }
    return false;
}

async function handleRegister(e) {
    e.preventDefault();
    const data = {
        name: document.getElementById('regName').value,
        email: document.getElementById('regEmail').value,
        password: document.getElementById('regPassword').value,
        phone: document.getElementById('regPhone').value,
        company_code: document.getElementById('regCompanyCode').value || null,
    };
    const btn = e.target.querySelector('button[type="submit"]');

    if (btn) { btn.disabled = true; btn.textContent = '가입 중...'; }
    try {
        const result = await API.register(data);
        API.setTokens(result.access_token, result.refresh_token);
        API.setUser(result.user);
        closeAuthModal();
        showToast('회원가입 완료!');
        updateAuthUI();
        refreshCurrentTab();
    } catch (err) {
        showToast(err.detail || '회원가입 실패');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '회원가입'; }
    }
    return false;
}

async function handleLogout() {
    try {
        await API.logout();
    } catch {}
    API.clearTokens();
    showToast('로그아웃 완료');
    updateAuthUI();
    if (typeof NotificationManager !== 'undefined') {
        NotificationManager.refreshBadge();
    }
    switchTab('map');
}

function updateAuthUI() {
    // 탭별 로그인 필요 UI 업데이트
    const user = API.getUser();
    document.querySelectorAll('.login-prompt').forEach(el => {
        el.style.display = user ? 'none' : 'block';
    });
}

function showToast(message) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
}
