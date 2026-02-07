import 'package:flutter/material.dart';
import '../../../app/constants.dart';
import '../../../core/utils/formatters.dart';
import '../../../data/models/store.dart';

class StoreCard extends StatelessWidget {
  final Store store;
  final VoidCallback? onTap;

  const StoreCard({super.key, required this.store, this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              _buildIcon(),
              const SizedBox(width: 12),
              Expanded(child: _buildInfo()),
              if (store.discounts.isNotEmpty) _buildDiscount(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildIcon() {
    final color = _parseColor(store.iconColor);
    return CircleAvatar(
      radius: 24,
      backgroundColor: color.withValues(alpha: 0.15),
      child: Text(
        store.iconLetter,
        style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 18),
      ),
    );
  }

  Widget _buildInfo() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          store.name,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 4),
        Text(
          store.brand,
          style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
        ),
        if (store.distanceM != null) ...[
          const SizedBox(height: 2),
          Text(
            Formatters.distance(store.distanceM!),
            style: const TextStyle(color: AppColors.textHint, fontSize: 12),
          ),
        ],
      ],
    );
  }

  Widget _buildDiscount() {
    final d = store.discounts.first;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        Formatters.discount(type: d.type, value: d.value),
        style: const TextStyle(
          color: AppColors.primary,
          fontWeight: FontWeight.w600,
          fontSize: 13,
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
