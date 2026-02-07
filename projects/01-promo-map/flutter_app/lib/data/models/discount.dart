class Discount {
  final int id;
  final int storeId;
  final int companyId;
  final String discountType;
  final double discountValue;
  final String description;
  final int minPurchase;
  final int maxDiscount;
  final String? validFrom;
  final String? validUntil;
  final bool isActive;
  final String? storeName;
  final String? storeBrand;
  final String? companyName;

  const Discount({
    required this.id,
    required this.storeId,
    required this.companyId,
    this.discountType = 'percent',
    required this.discountValue,
    this.description = '',
    this.minPurchase = 0,
    this.maxDiscount = 0,
    this.validFrom,
    this.validUntil,
    this.isActive = true,
    this.storeName,
    this.storeBrand,
    this.companyName,
  });

  factory Discount.fromJson(Map<String, dynamic> json) {
    return Discount(
      id: json['id'] as int,
      storeId: json['store_id'] as int,
      companyId: json['company_id'] as int,
      discountType: (json['discount_type'] as String?) ?? 'percent',
      discountValue: (json['discount_value'] as num).toDouble(),
      description: (json['description'] as String?) ?? '',
      minPurchase: (json['min_purchase'] as int?) ?? 0,
      maxDiscount: (json['max_discount'] as int?) ?? 0,
      validFrom: json['valid_from'] as String?,
      validUntil: json['valid_until'] as String?,
      isActive: (json['is_active'] as bool?) ?? true,
      storeName: json['store_name'] as String?,
      storeBrand: json['store_brand'] as String?,
      companyName: json['company_name'] as String?,
    );
  }
}
