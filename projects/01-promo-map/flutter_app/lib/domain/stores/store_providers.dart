import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/store.dart';
import '../../data/models/store_detail.dart';
import '../../data/models/paginated.dart';
import '../providers/providers.dart';
import '../location/location_provider.dart';

// Nearby stores based on current location
final nearbyStoresProvider = FutureProvider.autoDispose<List<Store>>((ref) async {
  final location = ref.watch(currentLocationProvider);
  final repo = ref.watch(storeRepositoryProvider);

  return location.when(
    data: (pos) => repo.getNearby(
      lat: pos.latitude,
      lon: pos.longitude,
      radius: 500,
    ),
    loading: () => <Store>[],
    error: (_, __) => <Store>[],
  );
});

// Nearby stores with category filter
final nearbyStoresWithCategoryProvider =
    FutureProvider.autoDispose.family<List<Store>, String?>((ref, category) async {
  final location = ref.watch(currentLocationProvider);
  final repo = ref.watch(storeRepositoryProvider);

  return location.when(
    data: (pos) => repo.getNearby(
      lat: pos.latitude,
      lon: pos.longitude,
      radius: 500,
      category: category,
    ),
    loading: () => <Store>[],
    error: (_, __) => <Store>[],
  );
});

// Search stores
final searchQueryProvider = StateProvider<String>((ref) => '');

final searchResultsProvider =
    FutureProvider.autoDispose<Paginated<Store>>((ref) async {
  final query = ref.watch(searchQueryProvider);
  final repo = ref.watch(storeRepositoryProvider);

  if (query.isEmpty) {
    return Paginated<Store>(items: [], total: 0, page: 1, size: 20, pages: 0);
  }

  return repo.search(query: query);
});

// Store detail
final storeDetailProvider =
    FutureProvider.autoDispose.family<StoreDetail, int>((ref, storeId) async {
  final repo = ref.watch(storeRepositoryProvider);
  return repo.getDetail(storeId);
});

// Selected category filter
final selectedCategoryProvider = StateProvider<String?>((ref) => null);
