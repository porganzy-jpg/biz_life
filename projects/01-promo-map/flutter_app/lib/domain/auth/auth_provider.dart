import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/providers.dart';
import 'auth_notifier.dart';
import 'auth_state.dart';

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.watch(authRepositoryProvider));
});
