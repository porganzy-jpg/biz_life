import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../app/constants.dart';
import '../../domain/stores/store_providers.dart';
import '../../domain/reviews/review_providers.dart';
import '../../domain/auth/auth_provider.dart';
import '../../core/ads/ad_manager.dart';
import '../widgets/store/discount_badge.dart';
import '../widgets/review/review_card.dart';
import '../widgets/review/star_rating.dart';
import '../widgets/review/review_form.dart';
import '../widgets/favorite/favorite_toggle.dart';
import '../widgets/common/app_loading.dart';
import '../widgets/common/app_error.dart';
import '../widgets/common/app_toast.dart';
import '../widgets/common/banner_ad_widget.dart';
import '../widgets/auth/auth_modal.dart';

class StoreDetailScreen extends ConsumerStatefulWidget {
  final int storeId;

  const StoreDetailScreen({super.key, required this.storeId});

  @override
  ConsumerState<StoreDetailScreen> createState() => _StoreDetailScreenState();
}

class _StoreDetailScreenState extends ConsumerState<StoreDetailScreen> {
  final _adManager = AdManager();
  static int _viewCount = 0;

  @override
  void initState() {
    super.initState();
    _adManager.loadInterstitial();
    // 매장 3번째 조회마다 전면 광고 표시
    _viewCount++;
    if (_viewCount % 3 == 0) {
      Future.delayed(const Duration(milliseconds: 500), () {
        _adManager.showInterstitial();
      });
    }
  }

  @override
  void dispose() {
    _adManager.dispose();
    super.dispose();
  }

  int get storeId => widget.storeId;

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(storeDetailProvider(storeId));
    final reviews = ref.watch(storeReviewsProvider(storeId));

    return Scaffold(
      appBar: AppBar(
        title: detail.when(
          data: (s) => Text(s.name),
          loading: () => const Text('매장 상세'),
          error: (_, __) => const Text('매장 상세'),
        ),
        actions: [
          FavoriteToggle(storeId: storeId),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: detail.when(
              data: (store) => SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
              // Store info header
              Container(
                padding: const EdgeInsets.all(20),
                color: AppColors.surface,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        CircleAvatar(
                          radius: 28,
                          backgroundColor: _parseColor(store.iconColor)
                              .withValues(alpha: 0.15),
                          child: Text(
                            store.iconLetter,
                            style: TextStyle(
                              color: _parseColor(store.iconColor),
                              fontWeight: FontWeight.bold,
                              fontSize: 22,
                            ),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                store.name,
                                style: const TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(
                                store.brand,
                                style: const TextStyle(
                                  color: AppColors.textSecondary,
                                  fontSize: 16,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    if (store.avgRating != null)
                      Row(
                        children: [
                          StarRating(
                            rating: store.avgRating!,
                            size: 20,
                            showValue: true,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            '(${store.reviewsCount})',
                            style: const TextStyle(
                              color: AppColors.textHint,
                              fontSize: 14,
                            ),
                          ),
                        ],
                      ),
                    const SizedBox(height: 12),
                    if (store.address.isNotEmpty)
                      _InfoRow(Icons.location_on_outlined, store.address),
                    if (store.phone.isNotEmpty)
                      _InfoRow(
                        Icons.phone_outlined,
                        store.phone,
                        onTap: () => launchUrl(Uri.parse('tel:${store.phone}')),
                      ),
                    _InfoRow(
                      Icons.category_outlined,
                      store.category,
                    ),
                  ],
                ),
              ),

              // Discounts section
              if (store.discounts.isNotEmpty) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(20),
                  color: AppColors.surface,
                  width: double.infinity,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '할인 혜택',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: store.discounts
                            .map((d) => DiscountBadge(discount: d, large: true))
                            .toList(),
                      ),
                    ],
                  ),
                ),
              ],

              // Reviews section
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(20),
                color: AppColors.surface,
                width: double.infinity,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Text(
                          '리뷰',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          '${store.reviewsCount}개',
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),

                    // Write review button
                    _WriteReviewSection(storeId: storeId),

                    const SizedBox(height: 8),

                    // Reviews list
                    reviews.when(
                      data: (result) {
                        if (result.items.isEmpty) {
                          return const Padding(
                            padding: EdgeInsets.symmetric(vertical: 24),
                            child: Center(
                              child: Text(
                                '아직 리뷰가 없습니다\n첫 리뷰를 작성해보세요!',
                                textAlign: TextAlign.center,
                                style: TextStyle(color: AppColors.textHint),
                              ),
                            ),
                          );
                        }
                        return Column(
                          children: result.items
                              .map((r) => ReviewCard(review: r))
                              .toList(),
                        );
                      },
                      loading: () => const Padding(
                        padding: EdgeInsets.all(24),
                        child: AppLoading(),
                      ),
                      error: (e, _) => Text('리뷰를 불러올 수 없습니다'),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
              loading: () => const AppLoading(),
              error: (e, _) => AppError(
                message: '매장 정보를 불러올 수 없습니다',
                onRetry: () => ref.invalidate(storeDetailProvider(storeId)),
              ),
            ),
          ),
          const BannerAdWidget(),
        ],
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

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String text;
  final VoidCallback? onTap;

  const _InfoRow(this.icon, this.text, {this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GestureDetector(
        onTap: onTap,
        child: Row(
          children: [
            Icon(icon, size: 18, color: AppColors.textSecondary),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                text,
                style: TextStyle(
                  color: onTap != null ? AppColors.primary : AppColors.textSecondary,
                  fontSize: 14,
                  decoration:
                      onTap != null ? TextDecoration.underline : null,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WriteReviewSection extends ConsumerStatefulWidget {
  final int storeId;
  const _WriteReviewSection({required this.storeId});

  @override
  ConsumerState<_WriteReviewSection> createState() =>
      _WriteReviewSectionState();
}

class _WriteReviewSectionState extends ConsumerState<_WriteReviewSection> {
  bool _showForm = false;

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final createState = ref.watch(createReviewProvider);

    if (!_showForm) {
      return OutlinedButton.icon(
        onPressed: () {
          if (!auth.isAuthenticated) {
            AuthModal.show(context);
            return;
          }
          setState(() => _showForm = true);
        },
        icon: const Icon(Icons.rate_review_outlined),
        label: const Text('리뷰 작성'),
      );
    }

    return ReviewForm(
      isLoading: createState.isLoading,
      onSubmit: (rating, content) async {
        final success = await ref.read(createReviewProvider.notifier).create(
              storeId: widget.storeId,
              rating: rating,
              content: content,
            );
        if (success && mounted) {
          setState(() => _showForm = false);
          ref.invalidate(storeReviewsProvider(widget.storeId));
          ref.invalidate(storeDetailProvider(widget.storeId));
          showAppToast(context, '리뷰가 등록되었습니다');
        }
      },
    );
  }
}
