import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../domain/auth/auth_provider.dart';
import '../../domain/favorites/favorites_provider.dart';
import '../widgets/favorite/favorite_card.dart';
import '../widgets/common/app_loading.dart';
import '../widgets/common/app_error.dart';
import '../widgets/common/app_empty.dart';
import '../widgets/auth/auth_modal.dart';
import '../widgets/common/banner_ad_widget.dart';

class FavoritesScreen extends ConsumerWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);

    if (!auth.isAuthenticated) {
      return Scaffold(
        appBar: AppBar(title: const Text('즐겨찾기')),
        body: AppEmpty(
          icon: Icons.favorite_outline,
          message: '로그인하면 즐겨찾기를 관리할 수 있습니다',
          actionLabel: '로그인',
          onAction: () => AuthModal.show(context),
        ),
      );
    }

    final favorites = ref.watch(favoritesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('즐겨찾기')),
      body: Column(
        children: [
          Expanded(
            child: favorites.when(
              data: (list) {
                if (list.isEmpty) {
                  return const AppEmpty(
                    icon: Icons.favorite_outline,
                    message: '즐겨찾기한 매장이 없습니다\n지도에서 마음에 드는 매장을 추가해보세요',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () => ref.read(favoritesProvider.notifier).load(),
                  child: ListView.builder(
                    padding: const EdgeInsets.only(top: 8, bottom: 16),
                    itemCount: list.length,
                    itemBuilder: (context, index) {
                      final fav = list[index];
                      return FavoriteCard(
                        favorite: fav,
                        onTap: () => context.push('/store/${fav.storeId}'),
                        onRemove: () =>
                            ref.read(favoritesProvider.notifier).toggle(fav.storeId),
                      );
                    },
                  ),
                );
              },
              loading: () => const AppLoading(),
              error: (e, _) => AppError(
                message: '즐겨찾기를 불러올 수 없습니다',
                onRetry: () => ref.read(favoritesProvider.notifier).load(),
              ),
            ),
          ),
          const BannerAdWidget(),
        ],
      ),
    );
  }
}
