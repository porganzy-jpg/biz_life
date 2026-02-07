import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/utils/validators.dart';
import '../../../domain/auth/auth_provider.dart';
import '../common/primary_button.dart';
import '../common/app_toast.dart';

class RegisterForm extends ConsumerStatefulWidget {
  final VoidCallback? onSuccess;
  const RegisterForm({super.key, this.onSuccess});

  @override
  ConsumerState<RegisterForm> createState() => _RegisterFormState();
}

class _RegisterFormState extends ConsumerState<RegisterForm> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _companyCodeController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _nameController.dispose();
    _phoneController.dispose();
    _companyCodeController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    await ref.read(authProvider.notifier).register(
          email: _emailController.text.trim(),
          password: _passwordController.text,
          name: _nameController.text.trim(),
          phone: _phoneController.text.trim(),
          companyCode: _companyCodeController.text.trim().isNotEmpty
              ? _companyCodeController.text.trim()
              : null,
        );

    if (!mounted) return;
    final state = ref.read(authProvider);
    if (state.isAuthenticated) {
      widget.onSuccess?.call();
    } else if (state.error != null) {
      showAppToast(context, state.error!, isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);

    return Form(
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
          const SizedBox(height: 12),
          TextFormField(
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
              labelText: '이메일',
              prefixIcon: Icon(Icons.email_outlined),
            ),
            validator: Validators.email,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _passwordController,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: '비밀번호',
              prefixIcon: Icon(Icons.lock_outlined),
            ),
            validator: Validators.password,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _phoneController,
            keyboardType: TextInputType.phone,
            decoration: const InputDecoration(
              labelText: '전화번호 (선택)',
              prefixIcon: Icon(Icons.phone_outlined),
            ),
            validator: Validators.phone,
          ),
          const SizedBox(height: 12),
          TextFormField(
            controller: _companyCodeController,
            decoration: const InputDecoration(
              labelText: '회사 코드 (선택)',
              prefixIcon: Icon(Icons.business_outlined),
            ),
          ),
          const SizedBox(height: 24),
          PrimaryButton(
            text: '회원가입',
            isLoading: auth.isLoading,
            onPressed: _submit,
          ),
        ],
      ),
    );
  }
}
