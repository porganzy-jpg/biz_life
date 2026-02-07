class Paginated<T> {
  final List<T> items;
  final int total;
  final int page;
  final int size;
  final int pages;

  const Paginated({
    required this.items,
    required this.total,
    required this.page,
    required this.size,
    required this.pages,
  });

  bool get hasMore => page < pages;

  factory Paginated.fromJson(
    Map<String, dynamic> json,
    T Function(Map<String, dynamic>) fromJsonT,
  ) {
    return Paginated(
      items: (json['items'] as List<dynamic>)
          .map((e) => fromJsonT(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int,
      page: json['page'] as int,
      size: json['size'] as int,
      pages: json['pages'] as int,
    );
  }
}
