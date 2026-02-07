import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/utils/debouncer.dart';
import '../../domain/stores/store_providers.dart';
import '../widgets/store/store_card.dart';
import '../widgets/common/app_empty.dart';
import '../widgets/common/skeleton_loading.dart';
import '../widgets/common/banner_ad_widget.dart';

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _searchController = TextEditingController();
  final _debouncer = Debouncer(delay: const Duration(milliseconds: 500));

  @override
  void dispose() {
    _searchController.dispose();
    _debouncer.dispose();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debouncer.run(() {
      ref.read(searchQueryProvider.notifier).state = query.trim();
    });
  }

  @override
  Widget build(BuildContext context) {
    final searchResults = ref.watch(searchResultsProvider);
    final query = ref.watch(searchQueryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('매장 검색')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: '매장명, 브랜드를 검색하세요',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          ref.read(searchQueryProvider.notifier).state = '';
                        },
                      )
                    : null,
              ),
            ),
          ),
          Expanded(
            child: query.isEmpty
                ? const AppEmpty(
                    icon: Icons.search,
                    message: '매장명이나 브랜드를 검색해보세요',
                  )
                : searchResults.when(
                    data: (result) {
                      if (result.items.isEmpty) {
                        return AppEmpty(
                          icon: Icons.search_off,
                          message: '"$query"에 대한 검색 결과가 없습니다',
                        );
                      }
                      return ListView.builder(
                        itemCount: result.items.length,
                        itemBuilder: (context, index) {
                          return StoreCard(
                            store: result.items[index],
                            onTap: () => context
                                .push('/store/${result.items[index].id}'),
                          );
                        },
                      );
                    },
                    loading: () => ListView.builder(
                      itemCount: 5,
                      itemBuilder: (_, __) => const StoreCardSkeleton(),
                    ),
                    error: (e, _) => Center(child: Text('오류: $e')),
                  ),
          ),
          const BannerAdWidget(),
        ],
      ),
    );
  }
}
