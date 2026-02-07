import 'package:dio/dio.dart';
import '../../models/favorite.dart';

class FavoriteApi {
  final Dio dio;

  FavoriteApi(this.dio);

  Future<List<Favorite>> getAll() async {
    final response = await dio.get('/api/v1/favorites');
    final favorites = (response.data['favorites'] as List<dynamic>)
        .map((e) => Favorite.fromJson(e as Map<String, dynamic>))
        .toList();
    return favorites;
  }

  Future<Favorite> add(int storeId) async {
    final response = await dio.post('/api/v1/favorites', data: {
      'store_id': storeId,
    });
    return Favorite.fromJson(response.data);
  }

  Future<void> remove(int storeId) async {
    await dio.delete('/api/v1/favorites/$storeId');
  }
}
