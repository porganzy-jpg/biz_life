import 'package:flutter/material.dart';
import '../../../app/constants.dart';
import '../../../core/utils/formatters.dart';
import '../../../data/models/discount_brief.dart';

class DiscountBadge extends StatelessWidget {
  final DiscountBrief discount;
  final bool large;

  const DiscountBadge({super.key, required this.discount, this.large = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: large ? 14 : 10,
        vertical: large ? 8 : 5,
      ),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(large ? 10 : 6),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            Formatters.discount(type: discount.type, value: discount.value),
            style: TextStyle(
              color: AppColors.primary,
              fontWeight: FontWeight.bold,
              fontSize: large ? 16 : 13,
            ),
          ),
          if (discount.description.isNotEmpty) ...[
            const SizedBox(height: 2),
            Text(
              discount.description,
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: large ? 12 : 10,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ],
        ],
      ),
    );
  }
}
