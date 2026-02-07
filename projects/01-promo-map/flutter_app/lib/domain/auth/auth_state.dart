import '../../data/models/user.dart';

enum AuthStatus { initial, authenticated, unauthenticated, loading }

class AuthState {
  final AuthStatus status;
  final User? user;
  final String? error;

  const AuthState({
    this.status = AuthStatus.initial,
    this.user,
    this.error,
  });

  const AuthState.initial() : this();

  const AuthState.loading()
      : this(status: AuthStatus.loading);

  AuthState.authenticated(User user)
      : this(status: AuthStatus.authenticated, user: user);

  const AuthState.unauthenticated({String? error})
      : this(status: AuthStatus.unauthenticated, error: error);

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isLoading => status == AuthStatus.loading;
}
