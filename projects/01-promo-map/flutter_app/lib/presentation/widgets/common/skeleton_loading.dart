import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';
import '../../../app/constants.dart';

class SkeletonLoading extends StatelessWidget {
  final double width;
  final double height;
  final double borderRadius;

  const SkeletonLoading({
    super.key,
    this.width = double.infinity,
    required this.height,
    this.borderRadius = 8,
  });

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: AppColors.divider,
      highlightColor: AppColors.background,
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: AppColors.divider,
          borderRadius: BorderRadius.circular(borderRadius),
        ),
      ),
    );
  }
}

class StoreCardSkeleton extends StatelessWidget {
  const StoreCardSkeleton({super.key});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const SkeletonLoading(width: 48, height: 48, borderRadius: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SkeletonLoading(height: 16, width: MediaQuery.of(context).size.width * 0.4),
                  const SizedBox(height: 8),
                  const SkeletonLoading(height: 12, width: 120),
                  const SizedBox(height: 6),
                  const SkeletonLoading(height: 12, width: 80),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
