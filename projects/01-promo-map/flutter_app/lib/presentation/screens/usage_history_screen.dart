import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../app/constants.dart';
import '../../core/utils/formatters.dart';
import '../../domain/user/user_providers.dart';
import '../widgets/common/app_loading.dart';
import '../widgets/common/app_error.dart';
import '../widgets/common/app_empty.dart';

class UsageHistoryScreen extends ConsumerWidget {
  const UsageHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(usageHistoryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('할인 사용 내역')),
      body: history.when(
        data: (result) {
          if (result.items.isEmpty) {
            return const AppEmpty(
              icon: Icons.receipt_long_outlined,
              message: '할인 사용 내역이 없습니다',
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: result.items.length,
            separatorBuilder: (_, __) => const Divider(),
            itemBuilder: (context, index) {
              final item = result.items[index];
              return ListTile(
                leading: CircleAvatar(
                  backgroundColor: AppColors.success.withValues(alpha: 0.1),
                  child: const Icon(Icons.savings_outlined,
                      color: AppColors.success),
                ),
                title: Text(
                  item.storeName,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                subtitle: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${item.storeBrand} · ${item.discountDescription}',
                      style: const TextStyle(fontSize: 13),
                    ),
                    Text(
                      Formatters.relativeTime(item.usedAt),
                      style: const TextStyle(
                        color: AppColors.textHint,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
                trailing: Text(
                  '-${Formatters.currency(item.savedAmount)}',
                  style: const TextStyle(
                    color: AppColors.success,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
                isThreeLine: true,
              );
            },
          );
        },
        loading: () => const AppLoading(),
        error: (e, _) => AppError(
          message: '내역을 불러올 수 없습니다',
          onRetry: () => ref.invalidate(usageHistoryProvider),
        ),
      ),
    );
  }
}
