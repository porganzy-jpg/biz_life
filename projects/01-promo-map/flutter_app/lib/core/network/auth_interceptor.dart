import 'package:dio/dio.dart';
import '../storage/secure_storage.dart';

class AuthInterceptor extends Interceptor {
  final Dio dio;
  final SecureStorageService storage;

  AuthInterceptor({required this.dio, required this.storage});

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await storage.getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      final refreshToken = await storage.getRefreshToken();
      if (refreshToken == null) {
        return handler.next(err);
      }

      try {
        final refreshDio = Dio(BaseOptions(baseUrl: dio.options.baseUrl));
        final response = await refreshDio.post(
          '/api/v1/auth/refresh',
          data: {'refresh_token': refreshToken},
        );

        final newAccessToken = response.data['access_token'] as String;
        final newRefreshToken = response.data['refresh_token'] as String;
        await storage.saveTokens(
          accessToken: newAccessToken,
          refreshToken: newRefreshToken,
        );

        err.requestOptions.headers['Authorization'] = 'Bearer $newAccessToken';
        final retryResponse = await dio.fetch(err.requestOptions);
        return handler.resolve(retryResponse);
      } catch (_) {
        await storage.clearTokens();
        return handler.next(err);
      }
    }
    handler.next(err);
  }
}
