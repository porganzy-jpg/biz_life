import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import '../../app/constants.dart';
import '../../data/models/store.dart';
import '../../domain/location/location_provider.dart';
import '../../domain/stores/store_providers.dart';
import '../widgets/store/store_card.dart';
import '../widgets/store/category_chip.dart';
import '../widgets/common/app_loading.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  GoogleMapController? _mapController;
  final DraggableScrollableController _sheetController =
      DraggableScrollableController();

  @override
  void dispose() {
    _mapController?.dispose();
    _sheetController.dispose();
    super.dispose();
  }

  Set<Marker> _buildMarkers(List<Store> stores) {
    return stores.map((store) {
      return Marker(
        markerId: MarkerId('store_${store.id}'),
        position: LatLng(store.latitude, store.longitude),
        infoWindow: InfoWindow(
          title: store.name,
          snippet: store.discounts.isNotEmpty
              ? '${store.discounts.first.value.round()}% 할인'
              : store.brand,
          onTap: () => context.push('/store/${store.id}'),
        ),
        icon: BitmapDescriptor.defaultMarkerWithHue(
          BitmapDescriptor.hueOrange,
        ),
      );
    }).toSet();
  }

  @override
  Widget build(BuildContext context) {
    final location = ref.watch(currentLocationProvider);
    final selectedCategory = ref.watch(selectedCategoryProvider);
    final nearbyStores = ref.watch(nearbyStoresWithCategoryProvider(selectedCategory));

    return Scaffold(
      body: Stack(
        children: [
          // Google Map
          location.when(
            data: (pos) => GoogleMap(
              initialCameraPosition: CameraPosition(
                target: LatLng(pos.latitude, pos.longitude),
                zoom: 15,
              ),
              myLocationEnabled: true,
              myLocationButtonEnabled: false,
              zoomControlsEnabled: false,
              mapToolbarEnabled: false,
              markers: nearbyStores.when(
                data: (stores) => _buildMarkers(stores),
                loading: () => {},
                error: (_, __) => {},
              ),
              onMapCreated: (controller) => _mapController = controller,
            ),
            loading: () => const AppLoading(message: '위치를 불러오는 중...'),
            error: (_, __) => const Center(child: Text('위치를 불러올 수 없습니다')),
          ),

          // Category filter bar
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            left: 0,
            right: 0,
            child: CategoryChipBar(
              categories: CategoryChipBar.defaultCategories,
              selected: selectedCategory,
              onSelected: (cat) =>
                  ref.read(selectedCategoryProvider.notifier).state = cat,
            ),
          ),

          // My location button
          Positioned(
            right: 16,
            bottom: MediaQuery.of(context).size.height * 0.35 + 16,
            child: FloatingActionButton.small(
              heroTag: 'myLocation',
              backgroundColor: AppColors.surface,
              onPressed: () {
                final pos = ref.read(currentLocationProvider).valueOrNull;
                if (pos != null) {
                  _mapController?.animateCamera(
                    CameraUpdate.newLatLng(LatLng(pos.latitude, pos.longitude)),
                  );
                }
              },
              child: const Icon(Icons.my_location, color: AppColors.primary),
            ),
          ),

          // Bottom sheet with nearby stores
          DraggableScrollableSheet(
            controller: _sheetController,
            initialChildSize: 0.3,
            minChildSize: 0.1,
            maxChildSize: 0.75,
            builder: (context, scrollController) {
              return Container(
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius:
                      const BorderRadius.vertical(top: Radius.circular(20)),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 10,
                      offset: const Offset(0, -2),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    // Handle
                    Container(
                      margin: const EdgeInsets.symmetric(vertical: 10),
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: AppColors.divider,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Row(
                        children: [
                          const Icon(Icons.store, color: AppColors.primary, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            '주변 매장',
                            style: TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          const Spacer(),
                          nearbyStores.when(
                            data: (stores) => Text(
                              '${stores.length}개',
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 14,
                              ),
                            ),
                            loading: () => const SizedBox.shrink(),
                            error: (_, __) => const SizedBox.shrink(),
                          ),
                        ],
                      ),
                    ),
                    const Divider(),
                    Expanded(
                      child: nearbyStores.when(
                        data: (stores) {
                          if (stores.isEmpty) {
                            return const Center(
                              child: Text(
                                '주변에 할인 매장이 없습니다',
                                style: TextStyle(color: AppColors.textHint),
                              ),
                            );
                          }
                          return ListView.builder(
                            controller: scrollController,
                            itemCount: stores.length,
                            itemBuilder: (context, index) {
                              return StoreCard(
                                store: stores[index],
                                onTap: () =>
                                    context.push('/store/${stores[index].id}'),
                              );
                            },
                          );
                        },
                        loading: () => const AppLoading(),
                        error: (e, _) => Center(child: Text('오류: $e')),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}
