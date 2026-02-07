import '../datasources/remote/discount_api.dart';
import '../models/discount.dart';
import '../models/paginated.dart';

class DiscountRepository {
  final DiscountApi api;

  DiscountRepository({required this.api});

  Future<List<Discount>> getActive() => api.getActive();

  Future<Paginated<Discount>> getMy({int page = 1, int size = 20}) =>
      api.getMy(page: page, size: size);
}
