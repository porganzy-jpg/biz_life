class Favorite {
  final int id;
  final int storeId;
  final String storeName;
  final String storeBrand;
  final String storeCategory;
  final String iconColor;
  final String iconLetter;

  const Favorite({
    required this.id,
    required this.storeId,
    required this.storeName,
    required this.storeBrand,
    this.storeCategory = 'general',
    this.iconColor = '#FF6B35',
    this.iconLetter = 'S',
  });

  factory Favorite.fromJson(Map<String, dynamic> json) {
    return Favorite(
      id: json['id'] as int,
      storeId: json['store_id'] as int,
      storeName: json['store_name'] as String,
      storeBrand: json['store_brand'] as String,
      storeCategory: (json['store_category'] as String?) ?? 'general',
      iconColor: (json['icon_color'] as String?) ?? '#FF6B35',
      iconLetter: (json['icon_letter'] as String?) ?? 'S',
    );
  }
}
