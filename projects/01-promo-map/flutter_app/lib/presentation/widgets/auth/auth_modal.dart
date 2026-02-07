import 'package:flutter/material.dart';
import 'login_form.dart';
import 'register_form.dart';

class AuthModal extends StatefulWidget {
  const AuthModal({super.key});

  static Future<void> show(BuildContext context) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const AuthModal(),
    );
  }

  @override
  State<AuthModal> createState() => _AuthModalState();
}

class _AuthModalState extends State<AuthModal> {
  bool _isLogin = true;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey[300],
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              _isLogin ? '로그인' : '회원가입',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            if (_isLogin) LoginForm(onSuccess: () => Navigator.pop(context))
            else RegisterForm(onSuccess: () => Navigator.pop(context)),
            const SizedBox(height: 16),
            TextButton(
              onPressed: () => setState(() => _isLogin = !_isLogin),
              child: Text(
                _isLogin ? '계정이 없으신가요? 회원가입' : '이미 계정이 있으신가요? 로그인',
              ),
            ),
          ],
        ),
      ),
    );
  }
}
