class Review {
  final int id;
  final int userId;
  final String userName;
  final int storeId;
  final int rating;
  final String content;
  final String createdAt;

  const Review({
    required this.id,
    required this.userId,
    required this.userName,
    required this.storeId,
    required this.rating,
    this.content = '',
    required this.createdAt,
  });

  factory Review.fromJson(Map<String, dynamic> json) {
    return Review(
      id: json['id'] as int,
      userId: json['user_id'] as int,
      userName: json['user_name'] as String,
      storeId: json['store_id'] as int,
      rating: json['rating'] as int,
      content: (json['content'] as String?) ?? '',
      createdAt: json['created_at'] as String,
    );
  }
}
