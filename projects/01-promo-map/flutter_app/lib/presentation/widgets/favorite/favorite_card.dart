import 'package:flutter/material.dart';
import '../../../app/constants.dart';
import '../../../data/models/favorite.dart';

class FavoriteCard extends StatelessWidget {
  final Favorite favorite;
  final VoidCallback? onTap;
  final VoidCallback? onRemove;

  const FavoriteCard({
    super.key,
    required this.favorite,
    this.onTap,
    this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final color = _parseColor(favorite.iconColor);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              CircleAvatar(
                radius: 24,
                backgroundColor: color.withValues(alpha: 0.15),
                child: Text(
                  favorite.iconLetter,
                  style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 18),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      favorite.storeName,
                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${favorite.storeBrand} · ${favorite.storeCategory}',
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                    ),
                  ],
                ),
              ),
              if (onRemove != null)
                IconButton(
                  icon: const Icon(Icons.favorite, color: AppColors.error),
                  onPressed: onRemove,
                ),
            ],
          ),
        ),
      ),
    );
  }

  Color _parseColor(String hex) {
    try {
      return Color(int.parse(hex.replaceFirst('#', '0xFF')));
    } catch (_) {
      return AppColors.primary;
    }
  }
}
