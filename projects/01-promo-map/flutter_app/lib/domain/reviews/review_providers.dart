import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/review.dart';
import '../../data/models/paginated.dart';
import '../providers/providers.dart';

final storeReviewsProvider =
    FutureProvider.autoDispose.family<Paginated<Review>, int>((ref, storeId) async {
  final repo = ref.watch(reviewRepositoryProvider);
  return repo.getStoreReviews(storeId: storeId);
});

class CreateReviewState {
  final bool isLoading;
  final String? error;
  final Review? review;

  const CreateReviewState({
    this.isLoading = false,
    this.error,
    this.review,
  });
}

class CreateReviewNotifier extends StateNotifier<CreateReviewState> {
  final Ref _ref;

  CreateReviewNotifier(this._ref) : super(const CreateReviewState());

  Future<bool> create({
    required int storeId,
    required int rating,
    String content = '',
  }) async {
    state = const CreateReviewState(isLoading: true);
    try {
      final repo = _ref.read(reviewRepositoryProvider);
      final review = await repo.create(
        storeId: storeId,
        rating: rating,
        content: content,
      );
      state = CreateReviewState(review: review);
      return true;
    } catch (e) {
      state = CreateReviewState(error: e.toString());
      return false;
    }
  }

  void reset() {
    state = const CreateReviewState();
  }
}

final createReviewProvider =
    StateNotifierProvider.autoDispose<CreateReviewNotifier, CreateReviewState>(
        (ref) {
  return CreateReviewNotifier(ref);
});
