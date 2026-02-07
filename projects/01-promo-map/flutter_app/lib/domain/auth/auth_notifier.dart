import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/repositories/auth_repository.dart';
import '../../data/models/user.dart';
import 'auth_state.dart';

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repository;

  AuthNotifier(this._repository) : super(const AuthState.initial());

  Future<void> checkAuth() async {
    final loggedIn = await _repository.isLoggedIn();
    if (!loggedIn) {
      state = const AuthState.unauthenticated();
    }
  }

  Future<void> register({
    required String email,
    required String password,
    required String name,
    String phone = '',
    String? companyCode,
  }) async {
    state = const AuthState.loading();
    try {
      final result = await _repository.register(
        email: email,
        password: password,
        name: name,
        phone: phone,
        companyCode: companyCode,
      );
      state = AuthState.authenticated(result.user);
    } on DioException catch (e) {
      final message = _extractError(e);
      state = AuthState.unauthenticated(error: message);
    }
  }

  Future<void> login({
    required String email,
    required String password,
  }) async {
    state = const AuthState.loading();
    try {
      final result = await _repository.login(email: email, password: password);
      state = AuthState.authenticated(result.user);
    } on DioException catch (e) {
      final message = _extractError(e);
      state = AuthState.unauthenticated(error: message);
    }
  }

  Future<void> logout() async {
    try {
      await _repository.logout();
    } finally {
      state = const AuthState.unauthenticated();
    }
  }

  void setAuthenticated(User user) {
    state = AuthState.authenticated(user);
  }

  String _extractError(DioException e) {
    if (e.response?.data != null && e.response!.data is Map) {
      return e.response!.data['detail']?.toString() ?? '오류가 발생했습니다';
    }
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return '서버 연결 시간이 초과되었습니다';
    }
    return '네트워크 오류가 발생했습니다';
  }
}
