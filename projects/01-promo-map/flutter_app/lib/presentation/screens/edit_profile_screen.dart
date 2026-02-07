import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/utils/validators.dart';
import '../../domain/auth/auth_provider.dart';
import '../../domain/user/user_providers.dart';
import '../../domain/providers/providers.dart';
import '../widgets/common/primary_button.dart';
import '../widgets/common/app_toast.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    final user = ref.read(authProvider).user;
    if (user != null) {
      _nameController.text = user.name;
      _phoneController.text = user.phone;
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);
    try {
      final repo = ref.read(userRepositoryProvider);
      final updated = await repo.updateProfile(
        name: _nameController.text.trim(),
        phone: _phoneController.text.trim(),
      );
      ref.read(authProvider.notifier).setAuthenticated(updated);
      ref.invalidate(userProfileProvider);

      if (mounted) {
        showAppToast(context, '프로필이 수정되었습니다');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        showAppToast(context, '프로필 수정에 실패했습니다', isError: true);
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('프로필 수정')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(
                  labelText: '이름',
                  prefixIcon: Icon(Icons.person_outlined),
                ),
                validator: Validators.name,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: '전화번호',
                  prefixIcon: Icon(Icons.phone_outlined),
                ),
                validator: Validators.phone,
              ),
              const SizedBox(height: 32),
              PrimaryButton(
                text: '저장',
                isLoading: _isLoading,
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
