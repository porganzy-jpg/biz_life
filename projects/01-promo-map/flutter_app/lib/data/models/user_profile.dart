class UserProfile {
  final int id;
  final String email;
  final String name;
  final String phone;
  final String? companyName;
  final bool isAdmin;
  final int favoritesCount;
  final int reviewsCount;
  final int usageCount;

  const UserProfile({
    required this.id,
    required this.email,
    required this.name,
    this.phone = '',
    this.companyName,
    this.isAdmin = false,
    this.favoritesCount = 0,
    this.reviewsCount = 0,
    this.usageCount = 0,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as int,
      email: json['email'] as String,
      name: json['name'] as String,
      phone: (json['phone'] as String?) ?? '',
      companyName: json['company_name'] as String?,
      isAdmin: (json['is_admin'] as bool?) ?? false,
      favoritesCount: (json['favorites_count'] as int?) ?? 0,
      reviewsCount: (json['reviews_count'] as int?) ?? 0,
      usageCount: (json['usage_count'] as int?) ?? 0,
    );
  }
}
