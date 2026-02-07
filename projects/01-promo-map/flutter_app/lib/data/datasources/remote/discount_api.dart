import 'package:dio/dio.dart';
import '../../models/discount.dart';
import '../../models/paginated.dart';

class DiscountApi {
  final Dio dio;

  DiscountApi(this.dio);

  Future<List<Discount>> getActive() async {
    final response = await dio.get('/api/v1/discounts/active');
    final discounts = (response.data['discounts'] as List<dynamic>)
        .map((e) => Discount.fromJson(e as Map<String, dynamic>))
        .toList();
    return discounts;
  }

  Future<Paginated<Discount>> getMy({int page = 1, int size = 20}) async {
    final response = await dio.get('/api/v1/discounts/my', queryParameters: {
      'page': page,
      'size': size,
    });
    return Paginated.fromJson(response.data, Discount.fromJson);
  }
}
