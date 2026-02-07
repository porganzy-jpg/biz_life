import 'package:dio/dio.dart';
import '../../models/user.dart';
import '../../models/user_profile.dart';
import '../../models/usage_history.dart';
import '../../models/paginated.dart';

class UserApi {
  final Dio dio;

  UserApi(this.dio);

  Future<UserProfile> getProfile() async {
    final response = await dio.get('/api/v1/users/me');
    return UserProfile.fromJson(response.data);
  }

  Future<User> updateProfile({String? name, String? phone}) async {
    final response = await dio.put('/api/v1/users/me', data: {
      if (name != null) 'name': name,
      if (phone != null) 'phone': phone,
    });
    return User.fromJson(response.data);
  }

  Future<Paginated<UsageHistory>> getUsageHistory({
    int page = 1,
    int size = 20,
  }) async {
    final response = await dio.get('/api/v1/users/me/usage-history',
        queryParameters: {
          'page': page,
          'size': size,
        });
    return Paginated.fromJson(response.data, UsageHistory.fromJson);
  }
}
