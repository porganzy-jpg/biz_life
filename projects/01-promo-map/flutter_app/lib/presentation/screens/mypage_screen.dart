import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../app/constants.dart';
import '../../domain/auth/auth_provider.dart';
import '../../domain/user/user_providers.dart';
import '../widgets/common/app_loading.dart';
import '../widgets/auth/auth_modal.dart';

class MypageScreen extends ConsumerWidget {
  const MypageScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);

    if (!auth.isAuthenticated) {
      return Scaffold(
        appBar: AppBar(title: const Text('마이페이지')),
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.person_outline, size: 64, color: AppColors.textHint),
              const SizedBox(height: 16),
              const Text(
                '로그인하면 다양한 기능을 이용할 수 있습니다',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 16),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => AuthModal.show(context),
                child: const Text('로그인 / 회원가입'),
              ),
            ],
          ),
        ),
      );
    }

    final profile = ref.watch(userProfileProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('마이페이지')),
      body: profile.when(
        data: (user) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Profile header
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 32,
                      backgroundColor: AppColors.primary.withValues(alpha: 0.15),
                      child: Text(
                        user.name.isNotEmpty ? user.name[0] : '?',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            user.name,
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            user.email,
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 14,
                            ),
                          ),
                          if (user.companyName != null)
                            Text(
                              user.companyName!,
                              style: const TextStyle(
                                color: AppColors.primary,
                                fontSize: 14,
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Stats
            Row(
              children: [
                _StatCard(
                  icon: Icons.favorite,
                  label: '즐겨찾기',
                  count: user.favoritesCount,
                ),
                const SizedBox(width: 12),
                _StatCard(
                  icon: Icons.rate_review,
                  label: '리뷰',
                  count: user.reviewsCount,
                ),
                const SizedBox(width: 12),
                _StatCard(
                  icon: Icons.receipt_long,
                  label: '사용내역',
                  count: user.usageCount,
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Menu items
            _MenuItem(
              icon: Icons.edit_outlined,
              label: '프로필 수정',
              onTap: () => context.push('/edit-profile'),
            ),
            _MenuItem(
              icon: Icons.history,
              label: '할인 사용 내역',
              onTap: () => context.push('/usage-history'),
            ),
            _MenuItem(
              icon: Icons.settings_outlined,
              label: '설정',
              onTap: () => context.push('/settings'),
            ),
            const SizedBox(height: 24),
            OutlinedButton(
              onPressed: () => ref.read(authProvider.notifier).logout(),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.error,
                side: const BorderSide(color: AppColors.error),
              ),
              child: const Text('로그아웃'),
            ),
          ],
        ),
        loading: () => const AppLoading(),
        error: (e, _) => Center(child: Text('오류: $e')),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final int count;

  const _StatCard({
    required this.icon,
    required this.label,
    required this.count,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            children: [
              Icon(icon, color: AppColors.primary),
              const SizedBox(height: 8),
              Text(
                '$count',
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                label,
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MenuItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  const _MenuItem({required this.icon, required this.label, this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: AppColors.textSecondary),
      title: Text(label),
      trailing: const Icon(Icons.chevron_right, color: AppColors.textHint),
      onTap: onTap,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    );
  }
}
