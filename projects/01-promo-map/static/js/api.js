/**
 * PromoMap API 클라이언트
 * JWT 자동 갱신 + fetch 래퍼
 */
const API = {
    baseUrl: '/api/v1',

    getToken() {
        return localStorage.getItem('pm_access_token');
    },

    getRefreshToken() {
        return localStorage.getItem('pm_refresh_token');
    },

    setTokens(access, refresh) {
        localStorage.setItem('pm_access_token', access);
        if (refresh) localStorage.setItem('pm_refresh_token', refresh);
    },

    clearTokens() {
        localStorage.removeItem('pm_access_token');
        localStorage.removeItem('pm_refresh_token');
        localStorage.removeItem('pm_user');
    },

    getUser() {
        const u = localStorage.getItem('pm_user');
        return u ? JSON.parse(u) : null;
    },

    setUser(user) {
        localStorage.setItem('pm_user', JSON.stringify(user));
    },

    isLoggedIn() {
        return !!this.getToken();
    },

    async request(path, options = {}) {
        const url = path.startsWith('/') ? path : `${this.baseUrl}/${path}`;
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        const token = this.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        let response = await fetch(url, { ...options, headers });

        // 토큰 만료 → 자동 갱신
        if (response.status === 401 && this.getRefreshToken()) {
            const refreshed = await this.refreshTokens();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${this.getToken()}`;
                response = await fetch(url, { ...options, headers });
            }
        }

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: '요청 실패' }));
            throw { status: response.status, ...err };
        }
        return response.json();
    },

    async refreshTokens() {
        try {
            const res = await fetch(`${this.baseUrl}/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: this.getRefreshToken() }),
            });
            if (!res.ok) {
                if (typeof showToast === 'function') {
                    showToast('세션이 만료되었습니다. 다시 로그인해주세요.');
                }
                this.clearTokens();
                return false;
            }
            const data = await res.json();
            this.setTokens(data.access_token, data.refresh_token);
            this.setUser(data.user);
            return true;
        } catch {
            if (typeof showToast === 'function') {
                showToast('세션이 만료되었습니다. 다시 로그인해주세요.');
            }
            this.clearTokens();
            return false;
        }
    },

    // Auth
    register(data) {
        return this.request('auth/register', { method: 'POST', body: JSON.stringify(data) });
    },
    login(data) {
        return this.request('auth/login', { method: 'POST', body: JSON.stringify(data) });
    },
    logout() {
        return this.request('auth/logout', { method: 'POST' });
    },

    // Stores
    getNearby(lat, lon, radius = 200) {
        return this.request(`stores/nearby?lat=${lat}&lon=${lon}&radius=${radius}`);
    },
    searchStores(q, page = 1) {
        return this.request(`stores/search?q=${encodeURIComponent(q)}&page=${page}`);
    },
    getAllStores(page = 1) {
        return this.request(`stores/all?page=${page}`);
    },
    getStoreDetail(id) {
        return this.request(`stores/${id}`);
    },

    // Discounts
    getActiveDiscounts() {
        return this.request('discounts/active');
    },
    getMyDiscounts(page = 1) {
        return this.request(`discounts/my?page=${page}`);
    },

    // Favorites
    getFavorites() {
        return this.request('favorites');
    },
    addFavorite(storeId) {
        return this.request('favorites', { method: 'POST', body: JSON.stringify({ store_id: storeId }) });
    },
    removeFavorite(storeId) {
        return this.request(`favorites/${storeId}`, { method: 'DELETE' });
    },

    // Reviews
    getReviews(storeId, page = 1) {
        return this.request(`reviews/${storeId}?page=${page}`);
    },
    createReview(data) {
        return this.request('reviews', { method: 'POST', body: JSON.stringify(data) });
    },

    // Users
    getProfile() {
        return this.request('users/me');
    },
    updateProfile(data) {
        return this.request('users/me', { method: 'PUT', body: JSON.stringify(data) });
    },
    getUsageHistory(page = 1) {
        return this.request(`users/me/usage-history?page=${page}`);
    },

    // Notifications
    checkNotifications(lat, lng) {
        return this.request('notifications/check', {
            method: 'POST',
            body: JSON.stringify({ lat, lng }),
        });
    },
    getUnreadNotifications(limit = 50) {
        return this.request(`notifications/unread?limit=${limit}`);
    },
    markNotificationRead(id) {
        return this.request(`notifications/${id}/read`, { method: 'POST' });
    },
    markAllNotificationsRead() {
        return this.request('notifications/read-all', { method: 'POST' });
    },
    dismissNotification(id) {
        return this.request(`notifications/${id}`, { method: 'DELETE' });
    },
    getNotificationPreferences() {
        return this.request('notifications/preferences');
    },
    updateNotificationPreferences(data) {
        return this.request('notifications/preferences', {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },
    useDiscount(storeId, discountId, savedAmount = 0) {
        return this.request(`notifications/use?store_id=${storeId}&discount_id=${discountId}&saved_amount=${savedAmount}`, { method: 'POST' });
    },

    // Redemption (할인 코드 발급/사용)
    generateRedemptionCode(storeId, discountId) {
        return this.request('redeem/generate', {
            method: 'POST',
            body: JSON.stringify({ store_id: storeId, discount_id: discountId }),
        });
    },
    validateRedemptionCode(code) {
        return this.request('redeem/validate', {
            method: 'POST',
            body: JSON.stringify({ code }),
        });
    },
    completeRedemption(code, amount) {
        return this.request('redeem/complete', {
            method: 'POST',
            body: JSON.stringify({ code, amount: amount || 0 }),
        });
    },
    getRedemptionHistory() {
        return this.request('redeem/history');
    },
    getRedemptionStats() {
        return this.request('redeem/stats');
    },

    // Trending
    getTrendingDiscounts(days = 7, limit = 10) {
        return this.request(`trending/discounts?days=${days}&limit=${limit}`);
    },
    getPopularStores(limit = 10) {
        return this.request(`trending/stores?limit=${limit}`);
    },
    getHotDeals(limit = 5) {
        return this.request(`trending/hot-deals?limit=${limit}`);
    },
    getSavingsLeaders(limit = 5) {
        return this.request(`trending/savings-leaders?limit=${limit}`);
    },
};
