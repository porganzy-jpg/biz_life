import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/constants.dart';
import '../../../domain/favorites/favorites_provider.dart';
import '../../../domain/auth/auth_provider.dart';
import '../auth/auth_modal.dart';

class FavoriteToggle extends ConsumerWidget {
  final int storeId;
  final double size;

  const FavoriteToggle({super.key, required this.storeId, this.size = 24});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.watch(favoritesProvider); // Rebuild when favorites change
    final isFav = ref.read(favoritesProvider.notifier).isFavorited(storeId);
    final auth = ref.watch(authProvider);

    return IconButton(
      icon: Icon(
        isFav ? Icons.favorite : Icons.favorite_border,
        color: isFav ? AppColors.error : AppColors.textHint,
        size: size,
      ),
      onPressed: () {
        if (!auth.isAuthenticated) {
          AuthModal.show(context);
          return;
        }
        ref.read(favoritesProvider.notifier).toggle(storeId);
      },
    );
  }
}
