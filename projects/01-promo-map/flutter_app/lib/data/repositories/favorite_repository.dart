import '../datasources/remote/favorite_api.dart';
import '../models/favorite.dart';

class FavoriteRepository {
  final FavoriteApi api;

  FavoriteRepository({required this.api});

  Future<List<Favorite>> getAll() => api.getAll();

  Future<Favorite> add(int storeId) => api.add(storeId);

  Future<void> remove(int storeId) => api.remove(storeId);
}
