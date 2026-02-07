import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../app/constants.dart';
import '../../domain/providers/providers.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  bool _notifications = true;
  double _radius = 500;

  @override
  void initState() {
    super.initState();
    final prefs = ref.read(preferencesProvider);
    _notifications = prefs.notificationsEnabled;
    _radius = prefs.locationRadius;
  }

  @override
  Widget build(BuildContext context) {
    final prefs = ref.read(preferencesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('설정')),
      body: ListView(
        children: [
          const _SectionHeader(title: '알림'),
          SwitchListTile(
            title: const Text('주변 할인 알림'),
            subtitle: const Text('근처 할인 매장이 있으면 알려드립니다'),
            value: _notifications,
            activeTrackColor: AppColors.primary,
            onChanged: (value) {
              setState(() => _notifications = value);
              prefs.setNotificationsEnabled(value);
            },
          ),

          const _SectionHeader(title: '위치'),
          ListTile(
            title: const Text('검색 반경'),
            subtitle: Text('${_radius.round()}m'),
            trailing: SizedBox(
              width: 200,
              child: Slider(
                value: _radius,
                min: 100,
                max: 2000,
                divisions: 19,
                label: '${_radius.round()}m',
                activeColor: AppColors.primary,
                onChanged: (value) {
                  setState(() => _radius = value);
                  prefs.setLocationRadius(value);
                },
              ),
            ),
          ),

          const _SectionHeader(title: '앱 정보'),
          const ListTile(
            title: Text('버전'),
            trailing: Text(
              AppStrings.version,
              style: TextStyle(color: AppColors.textSecondary),
            ),
          ),
          ListTile(
            title: const Text('개인정보 처리방침'),
            trailing: const Icon(Icons.chevron_right, color: AppColors.textHint),
            onTap: () {
              // TODO: Open privacy policy URL
            },
          ),
          ListTile(
            title: const Text('이용약관'),
            trailing: const Icon(Icons.chevron_right, color: AppColors.textHint),
            onTap: () {
              // TODO: Open terms URL
            },
          ),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader({required this.title});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
      child: Text(
        title,
        style: const TextStyle(
          color: AppColors.textSecondary,
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
