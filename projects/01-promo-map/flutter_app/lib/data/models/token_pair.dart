import 'user.dart';

class TokenPair {
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final User user;

  const TokenPair({
    required this.accessToken,
    required this.refreshToken,
    this.tokenType = 'bearer',
    required this.user,
  });

  factory TokenPair.fromJson(Map<String, dynamic> json) {
    return TokenPair(
      accessToken: json['access_token'] as String,
      refreshToken: (json['refresh_token'] as String?) ?? '',
      tokenType: (json['token_type'] as String?) ?? 'bearer',
      user: User.fromJson(json['user'] as Map<String, dynamic>),
    );
  }
}
