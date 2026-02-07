import '../datasources/remote/user_api.dart';
import '../models/user.dart';
import '../models/user_profile.dart';
import '../models/usage_history.dart';
import '../models/paginated.dart';

class UserRepository {
  final UserApi api;

  UserRepository({required this.api});

  Future<UserProfile> getProfile() => api.getProfile();

  Future<User> updateProfile({String? name, String? phone}) =>
      api.updateProfile(name: name, phone: phone);

  Future<Paginated<UsageHistory>> getUsageHistory({
    int page = 1,
    int size = 20,
  }) => api.getUsageHistory(page: page, size: size);
}
