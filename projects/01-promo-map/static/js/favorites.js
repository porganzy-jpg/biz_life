/**
 * PromoMap 즐겨찾기 탭
 */

async function loadFavorites() {
    const container = document.getElementById('favoritesList');

    if (!API.isLoggedIn()) {
        container.innerHTML =
            '<div class="login-prompt">'
            + '<p>즐겨찾기를 보려면 로그인이 필요합니다</p>'
            + '<button class="btn-primary" onclick="openAuthModal()">로그인</button>'
            + '</div>';
        return;
    }

    container.innerHTML = '<div class="loading-text">불러오는 중...</div>';

    try {
        const data = await API.getFavorites();
        if (!data.favorites || data.favorites.length === 0) {
            container.innerHTML = '<div class="empty-state">즐겨찾기한 매장이 없습니다</div>';
            return;
        }

        container.innerHTML = data.favorites.map(f => {
            const catInfo = getCategoryInfo(f.store_category);
            return '<div class="store-card">'
                + '<div class="card-icon" style="background:' + f.icon_color + '">'
                + f.icon_letter
                + '<span class="card-category-icon">' + catInfo.icon + '</span>'
                + '</div>'
                + '<div class="card-info" onclick="openStoreDetail(' + f.store_id + ')">'
                + '<div class="card-name">' + f.store_name + '</div>'
                + '<div class="card-meta">'
                + '<span class="category-badge">' + catInfo.icon + ' ' + catInfo.label + '</span> '
                + f.store_brand + ' · ' + (f.store_category || '')
                + '</div>'
                + '</div>'
                + '<div class="card-actions">'
                + '<button class="fav-btn active" onclick="removeFavFromList(' + f.store_id + ', this)">\u2665</button>'
                + '</div>'
                + '</div>';
        }).join('');
    } catch (e) {
        container.innerHTML = '<div class="empty-state">즐겨찾기를 불러올 수 없습니다</div>';
    }
}

async function removeFavFromList(storeId, btn) {
    try {
        await API.removeFavorite(storeId);
        const card = btn.closest('.store-card');
        card.style.opacity = '0';
        card.style.transition = 'opacity 0.3s';
        setTimeout(() => {
            card.remove();
            const container = document.getElementById('favoritesList');
            if (!container.querySelector('.store-card')) {
                container.innerHTML = '<div class="empty-state">즐겨찾기한 매장이 없습니다</div>';
            }
        }, 300);
        showToast('즐겨찾기 해제');
    } catch (e) {
        showToast('처리 실패');
    }
}
