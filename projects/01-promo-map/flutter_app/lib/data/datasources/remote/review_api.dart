import 'package:dio/dio.dart';
import '../../models/review.dart';
import '../../models/paginated.dart';

class ReviewApi {
  final Dio dio;

  ReviewApi(this.dio);

  Future<Paginated<Review>> getStoreReviews({
    required int storeId,
    int page = 1,
    int size = 20,
  }) async {
    final response = await dio.get('/api/v1/reviews/$storeId', queryParameters: {
      'page': page,
      'size': size,
    });
    return Paginated.fromJson(response.data, Review.fromJson);
  }

  Future<Review> create({
    required int storeId,
    required int rating,
    String content = '',
  }) async {
    final response = await dio.post('/api/v1/reviews', data: {
      'store_id': storeId,
      'rating': rating,
      'content': content,
    });
    return Review.fromJson(response.data);
  }
}
