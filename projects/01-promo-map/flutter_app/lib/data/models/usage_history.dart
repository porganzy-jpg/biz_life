class UsageHistory {
  final int id;
  final String storeName;
  final String storeBrand;
  final String discountDescription;
  final double discountValue;
  final double savedAmount;
  final String usedAt;

  const UsageHistory({
    required this.id,
    required this.storeName,
    required this.storeBrand,
    this.discountDescription = '',
    required this.discountValue,
    required this.savedAmount,
    required this.usedAt,
  });

  factory UsageHistory.fromJson(Map<String, dynamic> json) {
    return UsageHistory(
      id: json['id'] as int,
      storeName: json['store_name'] as String,
      storeBrand: json['store_brand'] as String,
      discountDescription: (json['discount_description'] as String?) ?? '',
      discountValue: (json['discount_value'] as num).toDouble(),
      savedAmount: (json['saved_amount'] as num).toDouble(),
      usedAt: json['used_at'] as String,
    );
  }
}
