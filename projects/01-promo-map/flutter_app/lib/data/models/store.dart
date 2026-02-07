import 'discount_brief.dart';

class Store {
  final int id;
  final String name;
  final String brand;
  final String category;
  final String address;
  final double latitude;
  final double longitude;
  final String phone;
  final String iconColor;
  final String iconLetter;
  final double? distanceM;
  final List<DiscountBrief> discounts;

  const Store({
    required this.id,
    required this.name,
    required this.brand,
    this.category = 'general',
    this.address = '',
    required this.latitude,
    required this.longitude,
    this.phone = '',
    this.iconColor = '#FF6B35',
    this.iconLetter = 'S',
    this.distanceM,
    this.discounts = const [],
  });

  factory Store.fromJson(Map<String, dynamic> json) {
    return Store(
      id: json['id'] as int,
      name: json['name'] as String,
      brand: json['brand'] as String,
      category: (json['category'] as String?) ?? 'general',
      address: (json['address'] as String?) ?? '',
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      phone: (json['phone'] as String?) ?? '',
      iconColor: (json['icon_color'] as String?) ?? '#FF6B35',
      iconLetter: (json['icon_letter'] as String?) ?? 'S',
      distanceM: json['distance_m'] != null
          ? (json['distance_m'] as num).toDouble()
          : null,
      discounts: (json['discounts'] as List<dynamic>?)
              ?.map((e) => DiscountBrief.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}
