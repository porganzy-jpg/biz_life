import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/favorite.dart';
import '../providers/providers.dart';

class FavoritesNotifier extends StateNotifier<AsyncValue<List<Favorite>>> {
  final Ref _ref;

  FavoritesNotifier(this._ref) : super(const AsyncValue.loading()) {
    load();
  }

  Future<void> load() async {
    state = const AsyncValue.loading();
    try {
      final repo = _ref.read(favoriteRepositoryProvider);
      final favorites = await repo.getAll();
      state = AsyncValue.data(favorites);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> toggle(int storeId) async {
    final current = state.valueOrNull ?? [];
    final isFavorited = current.any((f) => f.storeId == storeId);
    final repo = _ref.read(favoriteRepositoryProvider);

    if (isFavorited) {
      // Optimistic remove
      state = AsyncValue.data(
        current.where((f) => f.storeId != storeId).toList(),
      );
      try {
        await repo.remove(storeId);
      } catch (_) {
        state = AsyncValue.data(current); // Revert
      }
    } else {
      try {
        final fav = await repo.add(storeId);
        state = AsyncValue.data([...current, fav]);
      } catch (_) {
        // Keep current state
      }
    }
  }

  bool isFavorited(int storeId) {
    return state.valueOrNull?.any((f) => f.storeId == storeId) ?? false;
  }
}

final favoritesProvider =
    StateNotifierProvider<FavoritesNotifier, AsyncValue<List<Favorite>>>((ref) {
  return FavoritesNotifier(ref);
});
