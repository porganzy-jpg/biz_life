import '../datasources/remote/review_api.dart';
import '../models/review.dart';
import '../models/paginated.dart';

class ReviewRepository {
  final ReviewApi api;

  ReviewRepository({required this.api});

  Future<Paginated<Review>> getStoreReviews({
    required int storeId,
    int page = 1,
    int size = 20,
  }) => api.getStoreReviews(storeId: storeId, page: page, size: size);

  Future<Review> create({
    required int storeId,
    required int rating,
    String content = '',
  }) => api.create(storeId: storeId, rating: rating, content: content);
}
