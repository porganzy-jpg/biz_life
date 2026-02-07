import '../datasources/remote/auth_api.dart';
import '../models/token_pair.dart';
import '../../core/storage/secure_storage.dart';

class AuthRepository {
  final AuthApi api;
  final SecureStorageService storage;

  AuthRepository({required this.api, required this.storage});

  Future<TokenPair> register({
    required String email,
    required String password,
    required String name,
    String phone = '',
    String? companyCode,
  }) async {
    final result = await api.register(
      email: email,
      password: password,
      name: name,
      phone: phone,
      companyCode: companyCode,
    );
    await storage.saveTokens(
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
    );
    return result;
  }

  Future<TokenPair> login({
    required String email,
    required String password,
  }) async {
    final result = await api.login(email: email, password: password);
    await storage.saveTokens(
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
    );
    return result;
  }

  Future<void> logout() async {
    try {
      await api.logout();
    } finally {
      await storage.clearTokens();
    }
  }

  Future<bool> isLoggedIn() => storage.hasTokens();
}
