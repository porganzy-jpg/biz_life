import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/discount.dart';
import '../providers/providers.dart';

final activeDiscountsProvider =
    FutureProvider.autoDispose<List<Discount>>((ref) async {
  final repo = ref.watch(discountRepositoryProvider);
  return repo.getActive();
});
