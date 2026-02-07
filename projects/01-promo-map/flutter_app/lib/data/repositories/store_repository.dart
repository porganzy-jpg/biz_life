import '../datasources/remote/store_api.dart';
import '../models/store.dart';
import '../models/store_detail.dart';
import '../models/paginated.dart';

class StoreRepository {
  final StoreApi api;

  StoreRepository({required this.api});

  Future<List<Store>> getNearby({
    required double lat,
    required double lon,
    double radius = 500,
    String? category,
  }) => api.getNearby(lat: lat, lon: lon, radius: radius, category: category);

  Future<Paginated<Store>> search({
    required String query,
    int page = 1,
    int size = 20,
  }) => api.search(query: query, page: page, size: size);

  Future<Paginated<Store>> getAll({int page = 1, int size = 20}) =>
      api.getAll(page: page, size: size);

  Future<StoreDetail> getDetail(int storeId) => api.getDetail(storeId);
}
