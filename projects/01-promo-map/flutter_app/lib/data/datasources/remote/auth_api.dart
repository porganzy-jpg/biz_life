import 'package:dio/dio.dart';
import '../../models/token_pair.dart';

class AuthApi {
  final Dio dio;

  AuthApi(this.dio);

  Future<TokenPair> register({
    required String email,
    required String password,
    required String name,
    String phone = '',
    String? companyCode,
  }) async {
    final response = await dio.post('/api/v1/auth/register', data: {
      'email': email,
      'password': password,
      'name': name,
      'phone': phone,
      if (companyCode != null) 'company_code': companyCode,
    });
    return TokenPair.fromJson(response.data);
  }

  Future<TokenPair> login({
    required String email,
    required String password,
  }) async {
    final response = await dio.post('/api/v1/auth/login', data: {
      'email': email,
      'password': password,
    });
    return TokenPair.fromJson(response.data);
  }

  Future<TokenPair> refresh(String refreshToken) async {
    final response = await dio.post('/api/v1/auth/refresh', data: {
      'refresh_token': refreshToken,
    });
    return TokenPair.fromJson(response.data);
  }

  Future<void> logout() async {
    await dio.post('/api/v1/auth/logout');
  }
}
