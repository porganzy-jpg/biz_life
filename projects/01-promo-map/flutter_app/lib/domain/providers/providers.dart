import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/network/dio_client.dart';
import '../../core/network/auth_interceptor.dart';
import '../../core/storage/secure_storage.dart';
import '../../core/storage/preferences.dart';
import '../../data/datasources/remote/auth_api.dart';
import '../../data/datasources/remote/store_api.dart';
import '../../data/datasources/remote/discount_api.dart';
import '../../data/datasources/remote/favorite_api.dart';
import '../../data/datasources/remote/review_api.dart';
import '../../data/datasources/remote/user_api.dart';
import '../../data/datasources/remote/notification_api.dart';
import '../../data/repositories/auth_repository.dart';
import '../../data/repositories/store_repository.dart';
import '../../data/repositories/discount_repository.dart';
import '../../data/repositories/favorite_repository.dart';
import '../../data/repositories/review_repository.dart';
import '../../data/repositories/user_repository.dart';
import '../../data/repositories/notification_repository.dart';

// Core
final secureStorageProvider = Provider<SecureStorageService>((ref) {
  return SecureStorageService();
});

final preferencesProvider = Provider<PreferencesService>((ref) {
  return PreferencesService();
});

final dioClientProvider = Provider<DioClient>((ref) {
  return DioClient();
});

final dioProvider = Provider<Dio>((ref) {
  final client = ref.watch(dioClientProvider);
  final storage = ref.watch(secureStorageProvider);
  client.dio.interceptors.add(
    AuthInterceptor(dio: client.dio, storage: storage),
  );
  return client.dio;
});

// APIs
final authApiProvider = Provider<AuthApi>((ref) {
  return AuthApi(ref.watch(dioProvider));
});

final storeApiProvider = Provider<StoreApi>((ref) {
  return StoreApi(ref.watch(dioProvider));
});

final discountApiProvider = Provider<DiscountApi>((ref) {
  return DiscountApi(ref.watch(dioProvider));
});

final favoriteApiProvider = Provider<FavoriteApi>((ref) {
  return FavoriteApi(ref.watch(dioProvider));
});

final reviewApiProvider = Provider<ReviewApi>((ref) {
  return ReviewApi(ref.watch(dioProvider));
});

final userApiProvider = Provider<UserApi>((ref) {
  return UserApi(ref.watch(dioProvider));
});

final notificationApiProvider = Provider<NotificationApi>((ref) {
  return NotificationApi(ref.watch(dioProvider));
});

// Repositories
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    api: ref.watch(authApiProvider),
    storage: ref.watch(secureStorageProvider),
  );
});

final storeRepositoryProvider = Provider<StoreRepository>((ref) {
  return StoreRepository(api: ref.watch(storeApiProvider));
});

final discountRepositoryProvider = Provider<DiscountRepository>((ref) {
  return DiscountRepository(api: ref.watch(discountApiProvider));
});

final favoriteRepositoryProvider = Provider<FavoriteRepository>((ref) {
  return FavoriteRepository(api: ref.watch(favoriteApiProvider));
});

final reviewRepositoryProvider = Provider<ReviewRepository>((ref) {
  return ReviewRepository(api: ref.watch(reviewApiProvider));
});

final userRepositoryProvider = Provider<UserRepository>((ref) {
  return UserRepository(api: ref.watch(userApiProvider));
});

final notificationRepositoryProvider = Provider<NotificationRepository>((ref) {
  return NotificationRepository(api: ref.watch(notificationApiProvider));
});
