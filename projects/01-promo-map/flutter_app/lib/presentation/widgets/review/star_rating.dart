import 'package:flutter/material.dart';
import '../../../app/constants.dart';

class StarRating extends StatelessWidget {
  final double rating;
  final double size;
  final bool showValue;

  const StarRating({
    super.key,
    required this.rating,
    this.size = 20,
    this.showValue = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        ...List.generate(5, (index) {
          if (index < rating.floor()) {
            return Icon(Icons.star, color: AppColors.star, size: size);
          } else if (index < rating) {
            return Icon(Icons.star_half, color: AppColors.star, size: size);
          }
          return Icon(Icons.star_outline, color: AppColors.divider, size: size);
        }),
        if (showValue) ...[
          const SizedBox(width: 4),
          Text(
            rating.toStringAsFixed(1),
            style: TextStyle(
              color: AppColors.textSecondary,
              fontSize: size * 0.7,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ],
    );
  }
}
