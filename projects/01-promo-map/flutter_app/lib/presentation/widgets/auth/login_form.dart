import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/utils/validators.dart';
import '../../../domain/auth/auth_provider.dart';
import '../common/primary_button.dart';
import '../common/app_toast.dart';

class LoginForm extends ConsumerStatefulWidget {
  final VoidCallback? onSuccess;
  const LoginForm({super.key, this.onSuccess});

  @override
  ConsumerState<LoginForm> createState() => _LoginFormState();
}

class _LoginFormState extends ConsumerState<LoginForm> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    await ref.read(authProvider.notifier).login(
          email: _emailController.text.trim(),
          password: _passwordController.text,
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
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(
              labelText: '이메일',
              prefixIcon: Icon(Icons.email_outlined),
            ),
            validator: Validators.email,
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _passwordController,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: '비밀번호',
              prefixIcon: Icon(Icons.lock_outlined),
            ),
            validator: Validators.password,
          ),
          const SizedBox(height: 24),
          PrimaryButton(
            text: '로그인',
            isLoading: auth.isLoading,
            onPressed: _submit,
          ),
        ],
      ),
    );
  }
}
