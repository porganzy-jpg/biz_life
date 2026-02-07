class NotificationItem {
  final int storeId;
  final String storeName;
  final String storeBrand;
  final String discountDescription;
  final String discountType;
  final double discountValue;
  final double? distanceM;

  const NotificationItem({
    required this.storeId,
    required this.storeName,
    required this.storeBrand,
    this.discountDescription = '',
    this.discountType = 'percent',
    required this.discountValue,
    this.distanceM,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    return NotificationItem(
      storeId: json['store_id'] as int,
      storeName: json['store_name'] as String,
      storeBrand: json['store_brand'] as String,
      discountDescription: (json['discount_description'] as String?) ?? '',
      discountType: (json['discount_type'] as String?) ?? 'percent',
      discountValue: (json['discount_value'] as num).toDouble(),
      distanceM: json['distance_m'] != null
          ? (json['distance_m'] as num).toDouble()
          : null,
    );
  }
}
