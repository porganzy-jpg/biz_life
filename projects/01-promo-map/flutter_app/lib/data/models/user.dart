class User {
  final int id;
  final String email;
  final String name;
  final String phone;
  final String? companyName;
  final bool isAdmin;

  const User({
    required this.id,
    required this.email,
    required this.name,
    this.phone = '',
    this.companyName,
    this.isAdmin = false,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as int,
      email: json['email'] as String,
      name: json['name'] as String,
      phone: (json['phone'] as String?) ?? '',
      companyName: json['company_name'] as String?,
      isAdmin: (json['is_admin'] as bool?) ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'name': name,
        'phone': phone,
        'company_name': companyName,
        'is_admin': isAdmin,
      };
}
