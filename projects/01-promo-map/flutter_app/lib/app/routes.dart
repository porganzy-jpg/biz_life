import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../presentation/screens/splash_screen.dart';
import '../presentation/screens/shell_screen.dart';
import '../presentation/screens/map_screen.dart';
import '../presentation/screens/search_screen.dart';
import '../presentation/screens/favorites_screen.dart';
import '../presentation/screens/mypage_screen.dart';
import '../presentation/screens/store_detail_screen.dart';
import '../presentation/screens/edit_profile_screen.dart';
import '../presentation/screens/usage_history_screen.dart';
import '../presentation/screens/settings_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();
final _shellNavigatorKey = GlobalKey<NavigatorState>();

final appRouter = GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: '/splash',
  routes: [
    GoRoute(
      path: '/splash',
      builder: (context, state) => const SplashScreen(),
    ),
    ShellRoute(
      navigatorKey: _shellNavigatorKey,
      builder: (context, state, child) => ShellScreen(child: child),
      routes: [
        GoRoute(
          path: '/map',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: MapScreen(),
          ),
        ),
        GoRoute(
          path: '/search',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: SearchScreen(),
          ),
        ),
        GoRoute(
          path: '/favorites',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: FavoritesScreen(),
          ),
        ),
        GoRoute(
          path: '/mypage',
          pageBuilder: (context, state) => const NoTransitionPage(
            child: MypageScreen(),
          ),
        ),
      ],
    ),
    GoRoute(
      path: '/store/:id',
      builder: (context, state) {
        final id = int.parse(state.pathParameters['id']!);
        return StoreDetailScreen(storeId: id);
      },
    ),
    GoRoute(
      path: '/edit-profile',
      builder: (context, state) => const EditProfileScreen(),
    ),
    GoRoute(
      path: '/usage-history',
      builder: (context, state) => const UsageHistoryScreen(),
    ),
    GoRoute(
      path: '/settings',
      builder: (context, state) => const SettingsScreen(),
    ),
  ],
);
