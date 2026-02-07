import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/user_profile.dart';
import '../../data/models/usage_history.dart';
import '../../data/models/paginated.dart';
import '../providers/providers.dart';

final userProfileProvider =
    FutureProvider.autoDispose<UserProfile>((ref) async {
  final repo = ref.watch(userRepositoryProvider);
  return repo.getProfile();
});

final usageHistoryProvider =
    FutureProvider.autoDispose<Paginated<UsageHistory>>((ref) async {
  final repo = ref.watch(userRepositoryProvider);
  return repo.getUsageHistory();
});
