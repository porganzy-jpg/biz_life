import 'package:flutter/material.dart';
import '../../../app/constants.dart';
import '../../../core/utils/formatters.dart';
import '../../../data/models/review.dart';
import 'star_rating.dart';

class ReviewCard extends StatelessWidget {
  final Review review;

  const ReviewCard({super.key, required this.review});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.divider)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 16,
                backgroundColor: AppColors.primary.withValues(alpha: 0.1),
                child: Text(
                  review.userName.isNotEmpty ? review.userName[0] : '?',
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      review.userName,
                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                    ),
                    Text(
                      Formatters.relativeTime(review.createdAt),
                      style: const TextStyle(color: AppColors.textHint, fontSize: 12),
                    ),
                  ],
                ),
              ),
              StarRating(rating: review.rating.toDouble(), size: 14),
            ],
          ),
          if (review.content.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              review.content,
              style: const TextStyle(fontSize: 14, color: AppColors.textPrimary),
            ),
          ],
        ],
      ),
    );
  }
}
