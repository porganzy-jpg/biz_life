import 'package:dio/dio.dart';
import '../../models/store.dart';
import '../../models/store_detail.dart';
import '../../models/paginated.dart';

class StoreApi {
  final Dio dio;

  StoreApi(this.dio);

  Future<List<Store>> getNearby({
    required double lat,
    required double lon,
    double radius = 500,
    String? category,
  }) async {
    final response = await dio.get('/api/v1/stores/nearby', queryParameters: {
      'lat': lat,
      'lon': lon,
      'radius': radius,
      if (category != null) 'category': category,
    });
    final stores = (response.data['stores'] as List<dynamic>)
        .map((e) => Store.fromJson(e as Map<String, dynamic>))
        .toList();
    return stores;
  }

  Future<Paginated<Store>> search({
    required String query,
    int page = 1,
    int size = 20,
  }) async {
    final response = await dio.get('/api/v1/stores/search', queryParameters: {
      'q': query,
      'page': page,
      'size': size,
    });
    return Paginated.fromJson(response.data, Store.fromJson);
  }

  Future<Paginated<Store>> getAll({int page = 1, int size = 20}) async {
    final response = await dio.get('/api/v1/stores/all', queryParameters: {
      'page': page,
      'size': size,
    });
    return Paginated.fromJson(response.data, Store.fromJson);
  }

  Future<StoreDetail> getDetail(int storeId) async {
    final response = await dio.get('/api/v1/stores/$storeId');
    return StoreDetail.fromJson(response.data);
  }
}
