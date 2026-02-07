class DiscountBrief {
  final int id;
  final String type;
  final double value;
  final String description;

  const DiscountBrief({
    required this.id,
    required this.type,
    required this.value,
    this.description = '',
  });

  factory DiscountBrief.fromJson(Map<String, dynamic> json) {
    return DiscountBrief(
      id: json['id'] as int,
      type: (json['type'] as String?) ?? 'percent',
      value: (json['value'] as num).toDouble(),
      description: (json['description'] as String?) ?? '',
    );
  }
}
